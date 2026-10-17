"""Durable host receipts. No agent calls, retries, or work-item state writes."""
import hashlib
import json
import os
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import task_checks as checks

UTC = timezone.utc  # noqa: UP017 - Python 3.10 compatibility

ACTIONS = {
    'capacity': 'shrink or split scope before another host run; preserve original run and partial output',
    'timeout': 'query original run first; distinguish model request timeout from tool timeout; shrink oversized scope',
    'network': 'query original run and host policy; retry only within user limits, never blind resubmit',
    'tool': 'correct tool arguments or supported tool/model choice within host policy before retry',
    'acceptance': 'fix implementation or replan, then collect fresh verification; never repeat unchanged verification as a fix',
    'permission': 'block affected work until existing authority and original environment are available',
    'infrastructure': 'pause affected work; preserve exact error, original run, artifacts and recovery step; obey host protocol',
    'unknown': 'query original run and investigate cause before choosing an authorized retry or replan',
}
OUTCOMES = {'success', *ACTIONS}


def timestamp():
    return datetime.now(UTC).isoformat(timespec='seconds')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('coordination identifier must use letters, digits, underscores or hyphens')


def store_path(task_dir):
    return checks._safe_task_path(task_dir, 'audit/coordination.json')


def load(task_dir):
    path = store_path(task_dir)
    if not path.exists():
        return {'schema': 1, 'task_id': task_dir.name, 'runs': {}, 'events': {}, 'consumptions': {}}
    try:
        data = json.loads(path.read_text(), object_pairs_hook=checks.unique_json_object)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError('invalid coordination store') from error
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('task_id') != task_dir.name:
        raise ValueError('coordination store task/schema mismatch')
    for key in ['runs', 'events', 'consumptions']:
        if not isinstance(data.get(key), dict):
            checks.fail('invalid coordination store: '+key)
    for run, row in data['runs'].items():
        identifier(run)
        if not isinstance(row, dict) or row.get('run') != run or not all(row.get(k) for k in
                ['item', 'provider', 'inputs', 'inputs_sha256', 'manifest', 'contract_fingerprint', 'registered_at', 'recovery']):
            raise ValueError('invalid coordination run: '+run)
    for event, row in data['events'].items():
        identifier(event)
        if not isinstance(row, dict) or row.get('event') != event or row.get('run') not in data['runs'] or row.get('outcome') not in OUTCOMES:
            raise ValueError('invalid coordination event: '+event)
        checks.parse_evidence_time(row.get('observed_at', ''))
        artifact(task_dir, row.get('report', 'none'))
    for event, row in data['consumptions'].items():
        if event not in data['events'] or not isinstance(row, dict) or row.get('disposition') not in {'accepted', 'rejected'}:
            raise ValueError('invalid coordination consumption: '+event)
    return data


def save(task_dir, data):
    path = store_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = checks._safe_task_path(task_dir, 'audit/coordination-'+uuid.uuid4().hex+'.tmp')
    with temporary.open('x', encoding='utf-8') as output:
        json.dump(data, output, ensure_ascii=False, sort_keys=True, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def context(task_dir):
    contract = checks.check_contract(task_dir, mode='locked')
    fields = checks.check_state(task_dir, validate_inputs=False)
    if contract['work_items'] is None:
        raise ValueError('coordination requires work_items_schema: 1')
    return contract, fields


def artifact(task_dir, reference):
    if reference == 'none':
        return None
    path = checks._safe_task_path(task_dir, reference)
    if Path(reference).parts[0] not in {'evidence', 'outputs'}:
        raise ValueError('result report must be in evidence/ or outputs/')
    return path


def latest_runs(data):
    latest = {}
    # Persisted timestamps can tie, so registration order is explicit.
    for run, row in sorted(data['runs'].items(), key=lambda pair: pair[1]['sequence']):
        latest[row['item']] = run
    return latest


def pending_systemic(data):
    return any(row['systemic'] for event, row in data['events'].items() if event not in data['consumptions'])


def reservations(data):
    return {row['item']: run for run, row in data['runs'].items()
            if not any(event['run'] == run and key in data['consumptions'] for key, event in data['events'].items())}


def check_closed(task_dir):
    data = load(task_dir)
    if reservations(data):
        raise ValueError('coordination has unresolved original runs; query and reconcile before completion')
    if any(event not in data['consumptions'] for event in data['events']):
        raise ValueError('coordination has unconsumed notifications; reconcile before completion')


def dispatch(task_dir, args):
    import frontier
    contract, fields = context(task_dir)
    identifier(args.run)
    if args.item not in contract['work_items']['items']:
        raise ValueError('unknown work item: '+args.item)
    for value in [args.provider, args.recovery]:
        if not value or not value.strip():
            raise ValueError('provider and recovery must be non-empty')
    data = load(task_dir)
    if args.run in data['runs']:
        raise ValueError('run already registered; query original run, do not restart it')
    current = frontier.compute(task_dir)
    row = current['items'][args.item]
    if args.item not in current['ready'] and not (fields['status'] == 'in_progress' and row['status'] == 'in_progress'
            and row['owner'] == args.run and not row['conflicts'] and not pending_systemic(data)):
        raise ValueError('work item not dispatchable; inspect frontier and original run')
    if args.item in reservations(data):
        raise ValueError('original run is unresolved; query it before another dispatch')
    rows = checks.work_items.state_rows((task_dir/'state.md').read_text(), contract['work_items'], fields)
    for dep in checks.check_work_item_dependencies(contract, rows, args.item):
        checks.check_work_item_evidence(task_dir, task_dir/'state.md', contract, dep)
    if args.inputs == 'none':
        manifest = {'kind': 'contract-only', 'contract_revision': fields['contract_revision']}
        payload = json.dumps(manifest, sort_keys=True).encode()
    else:
        checks._check_inputs(task_dir, args.inputs, fields['contract_revision'])
        path = checks._safe_task_path(task_dir, args.inputs)
        payload = path.read_bytes()
        manifest = json.loads(payload, object_pairs_hook=checks.unique_json_object)
        if checks.parse_evidence_time(manifest.get('captured_at', '')) > checks.parse_evidence_time(timestamp()):
            raise ValueError('dispatch input capture must not be in the future')
    row = {'run': args.run, 'item': args.item, 'provider': args.provider, 'inputs': args.inputs,
           'inputs_sha256': hashlib.sha256(payload).hexdigest(), 'manifest': manifest,
           'contract_fingerprint': hashlib.sha256((task_dir/'contract.md').read_bytes()).hexdigest(),
           'registered_at': timestamp(), 'recovery': args.recovery, 'sequence': len(data['runs'])+1}
    data['runs'][args.run] = row
    save(task_dir, data)
    return row


def notify(task_dir, args):
    _, fields = context(task_dir)
    identifier(args.event)
    data = load(task_dir)
    if args.run not in data['runs']:
        raise ValueError('unknown original run: '+args.run)
    observed = checks.parse_evidence_time(args.observed_at)
    run = data['runs'][args.run]
    # Host may finish before it returns the run ID needed for registration.
    if observed > checks.parse_evidence_time(timestamp()):
        raise ValueError('event time must not be in the future')
    if args.outcome != 'success' and not args.error.strip():
        raise ValueError('failure notification requires exact error')
    if args.outcome == 'success' and args.report == 'none':
        raise ValueError('success notification requires result report reference')
    if args.systemic and args.outcome not in {'permission', 'infrastructure'}:
        raise ValueError('systemic stop requires permission or infrastructure failure')
    artifact(task_dir, args.report)
    row = {'event': args.event, 'run': args.run, 'item': run['item'], 'outcome': args.outcome,
           'report': args.report, 'observed_at': args.observed_at, 'error': args.error, 'systemic': args.systemic,
           'inputs_sha256': run['inputs_sha256']}
    if args.event in data['events']:
        if data['events'][args.event] != row:
            raise ValueError('event identifier reused with different content')
        return row
    if fields['status'] in {'done', 'cancelled'}:
        raise ValueError('task is terminal; new notifications cannot be queued')
    data['events'][args.event] = row
    save(task_dir, data)
    return row


def inbox(task_dir):
    context(task_dir)
    data = load(task_dir)
    failures = defaultdict(Counter)
    counted = set()
    for event in data['events'].values():
        # One host failure per original run, even if host sends multiple event identifiers.
        if event['outcome'] != 'success' and event['run'] not in counted:
            failures[event['item']][event['outcome']] += 1
            counted.add(event['run'])
    return {'pending': [row for event, row in data['events'].items() if event not in data['consumptions']],
            'runs': data['runs'], 'consumptions': data['consumptions'], 'failure_counts': dict(failures), 'actions': ACTIONS}


def consume(task_dir, args):
    contract, fields = context(task_dir)
    data = load(task_dir)
    if args.event not in data['events']:
        raise ValueError('unknown notification: '+args.event)
    if args.event in data['consumptions']:
        return data['consumptions'][args.event]
    event = data['events'][args.event]
    run = data['runs'][event['run']]
    if event['systemic'] and fields['status'] not in {'blocked', 'stopped', 'cancelled'}:
        raise ValueError('systemic failure: pause task with update before consuming notification')
    report = artifact(task_dir, event['report'])
    if report is not None and (not report.is_file() or not report.read_bytes().strip()):
        raise ValueError('result artifact missing or empty; leave notification pending')
    disposition, reason = 'accepted', 'artifact checked; register evidence and update original state separately'
    try:
        if fields['status'] in {'done', 'cancelled'}:
            raise ValueError('task is terminal; result retained for inspection')
        if latest_runs(data).get(run['item']) != event['run']:
            raise ValueError('original run superseded; salvage only after fresh verification')
        if run['item'] not in contract['work_items']['items']:
            raise ValueError('work item removed from current contract')
        if hashlib.sha256((task_dir/'contract.md').read_bytes()).hexdigest() != run['contract_fingerprint']:
            raise ValueError('dispatch contract changed')
        if run['inputs'] != 'none':
            inputs = checks._safe_task_path(task_dir, run['inputs'])
            if hashlib.sha256(inputs.read_bytes()).hexdigest() != run['inputs_sha256']:
                raise ValueError('dispatch input manifest changed')
            checks._check_inputs(task_dir, run['inputs'], fields['contract_revision'])
        rows = checks.work_items.state_rows((task_dir/'state.md').read_text(), contract['work_items'], fields)
        owner = rows[run['item']]['owner']
        if owner not in {'unassigned', event['run']}:
            raise ValueError('work item owner differs from original run')
        for dep in checks.check_work_item_dependencies(contract, rows, run['item']):
            checks.check_work_item_evidence(task_dir, task_dir/'state.md', contract, dep)
    except (OSError, ValueError) as error:
        disposition, reason = 'rejected', str(error)
    row = {'event': args.event, 'disposition': disposition, 'reason': reason, 'consumed_at': timestamp(),
           'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest() if report is not None else 'none',
           'next_action': ACTIONS.get(event['outcome'], 'register actual evidence; never treat notification as verified')}
    data['consumptions'][args.event] = row
    save(task_dir, data)
    return row
