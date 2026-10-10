#!/usr/bin/env python3
"""Read-only streaming statistics for Pi session JSONL. No prompt execution."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

NAMES = {'yxj-work': 'x-rail', 'x-rail': 'x-rail', 'yxj-work-long': 'x-rail-long', 'x-rail-long': 'x-rail-long'}
SUPPORTED = {'session', 'message', 'model_change', 'thinking_level_change', 'compaction', 'custom', 'branch_summary', 'label', 'session_info'}


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('event time needs timezone')
    if not value.endswith('Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError('invalid event timezone offset')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('event time needs timezone')
    return parsed.astimezone(timezone.utc)


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(x.get('text', '') for x in content if isinstance(x, dict) and x.get('type') == 'text')
    return ''


def invocation(text):
    stripped = text.lstrip()
    match = re.match(r'<skill\s+name=["\']([^"\']+)["\'][^>]*>(.*?)</skill>', stripped, re.S)
    if match and match.group(1) in NAMES:
        return match.group(1), hashlib.sha256(match.group(2).encode()).hexdigest()
    command = re.match(r'^/(yxj-work-long|x-rail-long|yxj-work|x-rail)(?:\s|$)', stripped)
    if command:
        return command.group(1), None
    return None


def error_kind(text):
    value = text.lower()
    patterns = [('timeout', r'time.?out|timed out|超时'), ('infrastructure', r'unknown agent|extension|runner|module.*not found|enoent|运行文件缺失'), ('parameter', r'invalid.*argument|validation|参数'), ('acceptance', r'acceptance|验收|assertion'), ('service', r'503|502|service|rate.limit|quota'), ('user_abort', r'abort|cancel|用户.*中止|interrupt')]
    return next((kind for kind, pattern in patterns if re.search(pattern, value)), 'unknown')


def new_episode(session_id, source, line, canonical, at, cross_window, model, thinking, task_id=None, association='unknown'):
    return {'session_id': session_id, 'source': source, 'line': line, 'canonical_name': canonical,
            'started_at': at.isoformat(), 'cross_window': cross_window, 'task_id': task_id,
            'association': association, 'first_artifact': None, 'first_supported_conclusion': None,
            'observed_assistant_span_seconds': 0, 'configurations': [{'model': model, 'thinking': thinking, 'at': at.isoformat()}],
            'timing': {'tool_wait_seconds': 0, 'wait_user_seconds': 0, 'manual_terminal_events': 0,
                       'thinking_seconds': None, 'unexplained_gap_seconds': None},
            'tool_outer_calls': 0, 'tool_nested_actions': 0, 'errors': [],
            '_start': at, '_last_assistant': None, '_done': None, '_tool_intervals': []}


def task_compliance(episodes, task_roots, mode):
    checker_dir = Path(__file__).resolve().parents[2] / 'x-rail/scripts'
    files = [checker_dir / name for name in ['task_checks.py', 'check-contract-legacy.sh', 'check-state-legacy.sh']]
    digest = hashlib.sha256(b''.join(file.read_bytes() for file in files)).hexdigest()
    spec = importlib.util.spec_from_file_location('self_check_tasks', files[0])
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    roots = [Path(root).resolve() for root in task_roots]
    if any(not root.is_dir() for root in roots):
        raise ValueError('task root must be a directory')
    results = []
    for task_id in sorted({ep['task_id'] for ep in episodes if ep['task_id']}):
        matches = [root / task_id for root in roots if (root / task_id).is_dir()]
        if len(matches) != 1:
            results.append({'task_id': task_id, 'status': 'not_run', 'reason': 'missing-or-ambiguous-task-root'})
            continue
        task = matches[0]
        if task.is_symlink() or not task.resolve().is_relative_to(task.parent.resolve()):
            results.append({'task_id': task_id, 'status': 'blocked', 'reason': 'task-path-boundary'})
            continue
        def snapshot():
            return {str(p.relative_to(task)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in task.rglob('*') if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(task.resolve())}
        before = snapshot()
        try:
            checks.check_contract(task, mode='locked' if mode == 'strict' else 'ready', strict=mode == 'strict')
            checks.check_state(task, strict=mode == 'strict')
            status = 'passed'
        except (OSError, ValueError):
            status = 'failed'
        unchanged = before == snapshot()
        results.append({'task_id': task_id, 'status': status if unchanged else 'blocked', 'records_unchanged': unchanged,
                        'meaning': 'format-check-only-not-historical-outcome'})
    return {'mode': mode, 'checker_sha256': digest, 'checks': results}


def analyze(sessions_root, *, start=None, end=None, days=7, timezone_name='Asia/Shanghai', project_roots=(), task_roots=(), task_mode=None):
    if bool(task_roots) != bool(task_mode) or (task_mode and task_mode not in {'strict', 'legacy-readonly'}):
        raise ValueError('task roots and explicit task mode must be paired')
    zone = ZoneInfo(timezone_name)
    finish = timestamp(end) if end else datetime.now(timezone.utc)
    begin = timestamp(start) if start else finish - timedelta(days=days)
    if begin >= finish:
        raise ValueError('start must precede end')
    root = Path(sessions_root).resolve()
    if not root.is_dir():
        raise ValueError('sessions root is not a directory')
    projects = [Path(p).resolve() for p in project_roots]
    coverage = {'parsed_files': 0, 'bad_lines': 0, 'unsupported_event_types': {}, 'duplicate_events': 0, 'uncertain_identity_events': 0, 'missing_event_times': 0, 'associated_task_count': 0, 'missing_artifacts': 0}
    unsupported = Counter()
    seen = set()
    invocations, episodes, errors = [], [], []
    relations = []
    outer = nested = 0
    for file in sorted(root.rglob('*.jsonl')):
        source = str(file.relative_to(root))
        session_id = source
        cwd = None
        model = thinking = None
        active = None
        calls = {}
        parsed_any = False
        with file.open(encoding='utf-8', errors='replace') as stream:
            for number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError('event must be object')
                except (ValueError, json.JSONDecodeError):
                    coverage['bad_lines'] += 1
                    continue
                parsed_any = True
                kind = record.get('type')
                if kind not in SUPPORTED:
                    unsupported[str(kind)] += 1
                    continue
                if kind == 'session':
                    session_id = record.get('id') or source
                    cwd = record.get('cwd')
                    if record.get('parentSession') and (not projects or (cwd and any(Path(cwd).resolve().is_relative_to(p) for p in projects))):
                        relations.append({'session_id': session_id, 'parent_session': record['parentSession'], 'source': source, 'line': number, 'association': 'explicit-log-reference-not-task-success'})
                    continue
                if projects and (not cwd or not any(Path(cwd).resolve().is_relative_to(p) for p in projects)):
                    continue
                if kind == 'model_change':
                    model = '/'.join(filter(None, [record.get('provider'), record.get('modelId')])) or None
                    if active:
                        active['configurations'].append({'model': model, 'thinking': thinking, 'at': record.get('timestamp')})
                    continue
                if kind == 'thinking_level_change':
                    thinking = record.get('thinkingLevel')
                    if active:
                        active['configurations'].append({'model': model, 'thinking': thinking, 'at': record.get('timestamp')})
                    continue
                if kind == 'custom':
                    subtype = record.get('customType', '')
                    if active and subtype in {'request_cancelled', 'request_timeout', 'request_error'}:
                        try:
                            custom_time = timestamp(record.get('timestamp'))
                        except (ValueError, TypeError):
                            coverage['missing_event_times'] += 1
                            continue
                        if begin <= custom_time < finish:
                            category = 'user_abort' if subtype == 'request_cancelled' else 'timeout' if subtype == 'request_timeout' else 'service'
                            error = {'category': category, 'source': source, 'line': number}
                            errors.append(error); active['errors'].append(error)
                    continue
                if kind != 'message':
                    continue
                try:
                    at = timestamp(record.get('timestamp'))
                except (ValueError, TypeError):
                    coverage['missing_event_times'] += 1
                    continue
                message = record.get('message') or {}
                role = message.get('role')
                event_id = record.get('id')
                if event_id:
                    identity = (session_id, event_id)
                    if identity in seen:
                        coverage['duplicate_events'] += 1
                        continue
                    seen.add(identity)
                else:
                    coverage['uncertain_identity_events'] += 1
                in_window = begin <= at < finish
                text = text_content(message.get('content'))
                if role == 'user':
                    call = invocation(text)
                    if call:
                        original, digest = call
                        active = new_episode(session_id, source, number, NAMES[original], at, at < begin, model, thinking)
                        calls = {}
                        if in_window:
                            entry = {'canonical_name': NAMES[original], 'original_name': original, 'source': source, 'line': number, 'event_id': event_id, 'at': at.isoformat(), 'skill_sha256': digest, 'model': model, 'thinking': thinking}
                            invocations.append(entry)
                            episodes.append(active)
                    elif active and in_window:
                        continuing = text.strip() in {'继续', 'continue', '继续吧', '按推荐'}
                        explicit_new = bool(re.match(r'^(?:新任务|另一个任务|new task)', text.strip(), re.I))
                        prior = active
                        if prior['_done']:
                            prior['timing']['wait_user_seconds'] += max(0, (at - prior['_done']).total_seconds())
                        if prior['_done'] or explicit_new:
                            active = new_episode(session_id, source, number, prior['canonical_name'], at,
                                prior['cross_window'] and continuing, model, thinking,
                                prior['task_id'] if continuing else None,
                                'continuation' if continuing else 'explicit-new-task' if explicit_new else 'unknown-followup')
                            episodes.append(active)
                            calls = {}
                        elif active not in episodes:
                            episodes.append(active)
                    continue
                if not in_window or active is None:
                    continue
                if active not in episodes:
                    episodes.append(active)
                if role == 'bashExecution':
                    active['timing']['manual_terminal_events'] += 1
                    continue
                blocks = message.get('content') if isinstance(message.get('content'), list) else []
                if role == 'assistant':
                    active['_last_assistant'] = at
                    active['observed_assistant_span_seconds'] = max(0, (at - active['_start']).total_seconds())
                    for block in blocks:
                        if not isinstance(block, dict) or block.get('type') != 'toolCall':
                            continue
                        name = block.get('name', '')
                        args = block.get('arguments') or {}
                        if not isinstance(args, dict):
                            args = {}
                        uses = args.get('tool_uses') or args.get('tools') or []
                        count = len(uses) if isinstance(uses, list) else 0
                        outer += 1; nested += count
                        active['tool_outer_calls'] += 1; active['tool_nested_actions'] += count
                        path = args.get('path') or args.get('file_path') or args.get('filePath')
                        if isinstance(path, str):
                            task_match = re.search(r'\.work-docs/tasks/([A-Za-z0-9_-]+)/', path)
                            if task_match:
                                active['task_id'] = task_match.group(1)
                                active['association'] = 'explicit-tool-path'
                        is_target = bool(isinstance(path, str) and name.split('.')[-1] in {'write', 'edit', 'apply_patch'} and not re.search(r'(?:contract|state|handoff)\.md$|/audit/|/evidence/', path))
                        calls[block.get('id')] = (at, is_target, number)
                    if message.get('stopReason') in {'stop', 'end_turn'}:
                        active['_done'] = at
                        if text and re.search(r'证据|依据|evidence|:[0-9]+', text) and active['first_supported_conclusion'] is None:
                            active['first_supported_conclusion'] = {'source': source, 'line': number, 'at': at.isoformat(), 'quality': 'candidate-not-semantic-proof'}
                    if message.get('errorMessage'):
                        category = error_kind(message['errorMessage'])
                        error = {'category': category, 'source': source, 'line': number}
                        errors.append(error); active['errors'].append(error)
                elif role == 'toolResult':
                    failed = message.get('isError') is True
                    call = calls.pop(message.get('toolCallId'), None)
                    if call:
                        called_at, is_target, call_line = call
                        active['_tool_intervals'].append((called_at, at))
                        if is_target and not failed and active['first_artifact'] is None:
                            active['first_artifact'] = {'source': source, 'line': number, 'call_line': call_line, 'at': at.isoformat(), 'quality': 'successful-target-write-not-content-verification'}
                    if failed:
                        error = {'category': error_kind(text), 'source': source, 'line': number}
                        errors.append(error); active['errors'].append(error)
        if parsed_any:
            coverage['parsed_files'] += 1
    for ep in episodes:
        if ep['first_artifact'] is None:
            coverage['missing_artifacts'] += 1
        intervals = sorted(ep.pop('_tool_intervals'))
        merged = []
        for begin_wait, end_wait in intervals:
            if end_wait < begin_wait:
                continue
            if merged and begin_wait <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end_wait))
            else:
                merged.append((begin_wait, end_wait))
        ep['timing']['tool_wait_seconds'] = sum((end_wait-begin_wait).total_seconds() for begin_wait,end_wait in merged)
        ep.pop('_start', None); ep.pop('_last_assistant', None); ep.pop('_done', None)
    coverage['associated_task_count'] = len({ep['task_id'] for ep in episodes if ep['task_id']})
    coverage['unsupported_event_types'] = dict(sorted(unsupported.items()))
    return {'schema_version': 1, 'window': {'start': begin.isoformat(), 'end': finish.isoformat(), 'timezone': timezone_name, 'local_start': begin.astimezone(zone).isoformat(), 'end_exclusive': True}, 'coverage': coverage, 'invocations': invocations, 'episodes': episodes, 'session_relations': relations, 'task_compliance': task_compliance(episodes, task_roots, task_mode) if task_roots else None, 'statistics': {'explicit_invocations': len(invocations), 'canonical_counts': dict(Counter(x['canonical_name'] for x in invocations)), 'tool_outer_calls': outer, 'tool_nested_actions': nested, 'error_events': errors, 'error_affected_episodes': sum(bool(ep['errors']) for ep in episodes), 'error_categories': dict(Counter(x['category'] for x in errors))}, 'limitations': ['No request-start timestamps: thinking time is unknown; observed spans are upper bounds, not active compute.', 'Task identity, parent-child links and unsupported shell writes remain unknown unless explicitly supported.', 'Supported-conclusion detection is a candidate marker, not factual quality grading.', 'Errors describe events, not failed task counts. Historical compliance does not imply historical outcome.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sessions-root', required=True)
    window = parser.add_mutually_exclusive_group()
    window.add_argument('--days', type=int)
    window.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--timezone', default='Asia/Shanghai')
    parser.add_argument('--project-root', action='append', default=[])
    parser.add_argument('--task-root', action='append', default=[])
    parser.add_argument('--task-mode', choices=['strict', 'legacy-readonly'])
    parser.add_argument('--format', choices=['json'], default='json')
    args = parser.parse_args()
    if bool(args.start) != bool(args.end) or (args.days is not None and args.end):
        parser.error('--start and --end must be paired and cannot use --days')
    if args.days is not None and args.days <= 0:
        parser.error('--days must be positive')
    try:
        result = analyze(args.sessions_root, start=args.start, end=args.end, days=args.days or 7, timezone_name=args.timezone, project_roots=args.project_root, task_roots=args.task_root, task_mode=args.task_mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as error:
        print(f'analyze-sessions: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
