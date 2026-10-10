#!/usr/bin/env python3
"""Safe task lifecycle commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_checks


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def complete(task_dir: Path, candidate: Path, before_commit=None) -> None:
    task_dir = Path(task_dir).resolve()
    candidate = Path(candidate)
    if not inside(candidate, task_dir) or candidate.resolve() == (task_dir / "state.md").resolve():
        raise ValueError("candidate must be a distinct file inside task directory")
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("candidate must be a regular file")
    formal = task_dir / "state.md"
    contract = task_dir / 'contract.md'
    if formal.is_symlink() or contract.is_symlink():
        raise ValueError('formal state and contract must not be symlinks')
    original = formal.read_bytes()
    original_contract = contract.read_bytes()
    candidate_bytes = candidate.read_bytes()
    if candidate.stat().st_dev != formal.stat().st_dev:
        raise ValueError('candidate must use the same filesystem')
    result = task_checks.check_state(task_dir, candidate)
    if result['status'] != 'done':
        raise ValueError('candidate must set status: done')
    if before_commit:
        before_commit()
    if formal.read_bytes() != original or contract.read_bytes() != original_contract or candidate.read_bytes() != candidate_bytes:
        raise ValueError("state, contract or candidate changed before commit")
    task_checks.check_state(task_dir, candidate)
    os.replace(candidate, formal)
    index = task_dir.parent.parent / 'index.md'
    if index.is_file():
        try:
            import re
            text = index.read_text()
            text = re.sub(r'(\| ' + re.escape(task_dir.name) + r' \|[^\n]*?\| )in_progress( \|)', r'\1done\2', text)
            index.write_text(text)
        except OSError as error:
            print(f'task: completed; index repair needed: {error}', file=sys.stderr)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def state_text(text: str, updates: dict[str, str]) -> str:
    for key, value in updates.items():
        if '\n' in value or '\r' in value:
            raise ValueError(f'{key} must use one line')
        expression = r'^' + re.escape(key) + r': .*$'
        if re.search(expression, text, re.M):
            text = re.sub(expression, lambda _: f'{key}: {value}', text, flags=re.M)
        else:
            text = text.rstrip('\n') + f'\n{key}: {value}\n'
    return text


def candidate_file(task_dir: Path, text: str) -> Path:
    directory = task_checks._safe_task_path(task_dir, 'tmp')
    directory.mkdir(exist_ok=True)
    candidate = directory / f'state-{uuid.uuid4().hex}.md'
    with candidate.open('x', encoding='utf-8') as output:
        output.write(text)
    return candidate


def start(task_dir: Path) -> None:
    formal = task_dir / 'state.md'
    if formal.exists() or formal.is_symlink():
        raise ValueError('state.md already exists; resume the existing task')
    data = task_checks.check_contract(task_dir, mode='ready')
    task_checks._safe_task_path(task_dir, 'audit')
    task_checks.check_contract(task_dir, mode='seal')
    fields = data['fields']
    timestamp = now()
    limit = {'L1': 60, 'L2': 150, 'L3': 400, 'long': 400}[fields['level']]
    values = {'task_id': task_dir.name, 'level': fields['level'], 'stage': fields['task_type'],
              'status': 'in_progress', 'contract_revision': fields['contract_revision'],
              'contract_fingerprint': hashlib.sha256((task_dir / 'contract.md').read_bytes()).hexdigest(),
              'evidence_schema': '2', 'done_when': fields['done_when'], 'budget': f'untracked/{limit}',
              'calls_since_progress': '0', 'last_progress_at': timestamp, 'updated_at': timestamp,
              'blocked_by': 'none', 'unblock_condition': 'none', 'next_action': fields['objective']}
    if fields['level'] in {'L3', 'long'}:
        values['started_at'] = timestamp
        values['deadline_at'] = (datetime.fromisoformat(timestamp) + timedelta(hours=8)).isoformat(timespec='seconds')
    text = ''.join(f'{key}: {value}\n' for key, value in values.items())
    text += ''.join(f'required_verification: {aid} status=not_run\n' for aid, item in data['acceptances'].items() if item['required'] == 'yes')
    candidate = candidate_file(task_dir, text)
    task_checks.check_state(task_dir, candidate)
    # Exclusive creation keeps an existing task intact, even if it appeared during setup.
    with formal.open('x', encoding='utf-8') as output:
        output.write(text)


def finish(task_dir: Path, used: int | None = None) -> None:
    fields = task_checks.check_state(task_dir)
    if fields['status'] != 'in_progress':
        raise ValueError('finish requires an in_progress task')
    original = (task_dir / 'state.md').read_bytes()
    updates = {'status': 'done', 'updated_at': now()}
    if used is not None:
        updates['tool_count_note'] = str(used)
    candidate = candidate_file(task_dir, state_text(original.decode(), updates))
    if (task_dir / 'state.md').read_bytes() != original:
        raise ValueError('state changed while preparing completion')
    complete(task_dir, candidate)


def run_verification(task_dir: Path, args) -> None:
    fields = task_checks.check_state(task_dir)
    if fields['status'] != 'in_progress':
        raise ValueError('run requires an in_progress task')
    contract = task_checks.check_contract(task_dir, mode='locked')
    acceptance = contract['acceptances'].get(args.acceptance)
    if not acceptance or acceptance['required'] != 'yes' or acceptance['verification_type'] != 'automatic':
        raise ValueError('run requires a required automatic acceptance; manual/consumer/external checks stay explicit')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.evidence):
        raise ValueError('evidence name must use letters, digits, underscores or hyphens')
    if not args.verification_command.strip() or args.timeout <= 0 or any(not value for value in args.expect):
        raise ValueError('command, expected output and positive timeout are required')
    root = Path(args.workspace).resolve()
    if not root.is_dir() or not task_dir.is_relative_to(root):
        raise ValueError('task directory must be inside workspace')
    manifest = {'version': 1, 'contract_revision': int(fields['contract_revision']),
                'workspace_root': str(root), 'files': []}
    latest = 0.0
    seen = set()
    for relative in args.input:
        raw = Path(relative)
        path = (root / raw).resolve()
        if raw.is_absolute() or '..' in raw.parts or not path.is_relative_to(root):
            raise ValueError(f'input path escapes workspace: {relative}')
        if path in seen:
            raise ValueError('duplicate input path')
        seen.add(path)
        if path in {task_dir / 'state.md', task_dir / 'contract.md'} or any(path.is_relative_to(task_dir / part) for part in ['evidence', 'audit', 'tmp']):
            raise ValueError('input summary cannot include task state or evidence')
        if path.is_file():
            manifest['files'].append({'path': relative, 'state': 'present', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            latest = max(latest, path.stat().st_mtime)
        elif not path.exists() and not path.is_symlink():
            manifest['files'].append({'path': relative, 'state': 'absent'})
        else:
            raise ValueError(f'input must be a file or explicitly absent: {relative}')
    directory = task_checks._safe_task_path(task_dir, 'evidence')
    directory.mkdir(exist_ok=True)
    receipt = task_checks._safe_task_path(task_dir, f'evidence/{args.evidence}.txt')
    inputs = task_checks._safe_task_path(task_dir, f'evidence/{args.evidence}.inputs.json')
    for path in [receipt, inputs]:
        if path.exists() or path.is_symlink():
            raise ValueError('evidence already exists; use a new name for a new attempt')
    updates = {'budget': fields['budget'], 'updated_at': now()}
    if args.used is not None:
        updates['tool_count_note'] = str(args.used)
    original = (task_dir / 'state.md').read_bytes()
    contract_bytes = (task_dir / 'contract.md').read_bytes()
    with inputs.open('x', encoding='utf-8') as output:
        json.dump(manifest, output, ensure_ascii=False, indent=2)
    task_checks._check_inputs(task_dir, str(inputs.relative_to(task_dir)), fields['contract_revision'])
    with receipt.open('x', encoding='utf-8') as output:
        output.write(f'command: {json.dumps(args.verification_command, ensure_ascii=False)}\nexpected: {args.expect!r}\n')
        output.flush()
        process = subprocess.Popen(['/bin/bash', '-o', 'pipefail', '-c', args.verification_command], cwd=root,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            code = 124
            output.write('\nverification timed out\n')
        output.write(f'\nexit_code: {code}\n')
    observed = receipt.read_text(errors='replace')
    # Match only command output, not the expected-value header.
    observed = observed.split('\n', 2)[2].rsplit('\nexit_code:', 1)[0]
    passed = code == 0 and all(value in observed for value in args.expect)
    timestamp = now()
    task_checks._check_inputs(task_dir, str(inputs.relative_to(task_dir)), fields['contract_revision'])
    if (task_dir / 'state.md').read_bytes() != original or (task_dir / 'contract.md').read_bytes() != contract_bytes:
        raise ValueError('state or contract changed during verification')
    updates['updated_at'] = timestamp
    if passed:
        updates.update({'calls_since_progress': '0', 'last_progress_at': timestamp})
    text = state_text(original.decode(), updates)
    text = re.sub(r'^required_verification: ' + re.escape(args.acceptance) + r' .*\n?', '', text, flags=re.M)
    status = 'passed' if passed else 'failed'
    text += f'required_verification: {args.acceptance} status={status} evidence=evidence/{args.evidence}.txt\n'
    last_edit = datetime.fromtimestamp(latest, timezone.utc).isoformat(timespec='seconds')
    text += (f'evidence:{args.evidence}|acceptance={args.acceptance}|command={args.verification_command.replace(chr(10), " ").replace(chr(13), " ").replace("|", "%7C")}'
             f'|run_at={timestamp}|result={status}|last_edit_at={last_edit}|inputs=evidence/{args.evidence}.inputs.json|contract_revision={fields["contract_revision"]}\n')
    candidate = candidate_file(task_dir, text)
    task_checks.check_state(task_dir, candidate)
    if (task_dir / 'state.md').read_bytes() != original or (task_dir / 'contract.md').read_bytes() != contract_bytes:
        raise ValueError('state or contract changed before recording result')
    os.replace(candidate, task_dir / 'state.md')
    if not passed:
        raise ValueError(f'verification failed; inspect evidence/{args.evidence}.txt')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["seal", "check"]:
        p = sub.add_parser(name)
        p.add_argument("task_dir")
    p = sub.add_parser("complete")
    p.add_argument("task_dir")
    p.add_argument("--candidate", required=True)
    p = sub.add_parser('start', help='generate initial state from an existing contract and seal it')
    p.add_argument('task_dir')
    p = sub.add_parser('finish', help='prepare a completion candidate and reuse strict checks')
    p.add_argument('task_dir')
    p.add_argument('--used', type=int, help='optional executor observation; not a completion or budget gate')
    p = sub.add_parser('run', help='run an automatic verification against bound inputs')
    p.add_argument('task_dir')
    p.add_argument('--acceptance', required=True)
    p.add_argument('--evidence', required=True, help='new receipt name without extension')
    p.add_argument('--workspace', required=True)
    p.add_argument('--input', action='append', required=True, help='relevant workspace-relative file; repeat as needed')
    p.add_argument('--expect', action='append', required=True, help='literal expected command output; repeat as needed')
    p.add_argument('--used', type=int, help='optional executor observation; not a completion or budget gate')
    p.add_argument('--command', dest='verification_command', required=True, help='explicit shell verification; check/complete never run this text')
    p.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    try:
        task_dir = Path(args.task_dir).resolve()
        if args.command == "seal":
            task_checks.check_contract(task_dir, mode="seal")
        elif args.command == "check":
            task_checks.check_contract(task_dir, mode="locked")
            task_checks.check_state(task_dir)
        elif args.command == 'start':
            start(task_dir)
        elif args.command == 'run':
            run_verification(task_dir, args)
        elif args.command == 'finish':
            finish(task_dir, args.used)
        else:
            candidate = Path(args.candidate)
            complete(task_dir, candidate)
        print(f"task: {args.command} passed")
        return 0
    except (OSError, ValueError) as error:
        print(f"task: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
