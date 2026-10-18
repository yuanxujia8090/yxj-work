"""Read-only execution frontier; state and evidence remain canonical."""
from pathlib import Path, PurePosixPath

import coordination
import task_checks as checks
import work_items


def scope_parts(scope):
    parts = PurePosixPath(scope.replace('\\', '/'))
    if parts.is_absolute() or '..' in parts.parts or not parts.parts:
        raise ValueError(f'scope must be workspace relative: {scope}')
    return parts.parts


def overlap(left, right):
    """A wildcard segment can cover descendants; uncertain overlap reserves both."""
    a, b = scope_parts(left), scope_parts(right)
    for index in range(min(len(a), len(b))):
        first, second = a[index], b[index]
        if any(char in first + second for char in '*?['):
            return True
        if first != second:
            return False
    return True


def compute(task_dir: Path):
    contract = checks.check_contract(task_dir, mode='locked')
    state = task_dir/'state.md'
    if state.is_symlink():
        raise ValueError('state must not be a symlink')
    fields, _, _ = checks._parse_state(state)
    checks.check_state(task_dir, validate_inputs=False)
    definition = contract['work_items']
    rows = work_items.state_rows(state.read_text(), definition, fields)
    if definition is None:
        raise ValueError('frontier requires work_items_schema: 1')
    def validity(name):
        return checks.check_work_item_evidence(task_dir, state, contract, name)
    ready, errors = work_items.candidates(definition, rows, validity)
    scopes = {name: work_items.references(item['scope'], identifiers=False) for name, item in definition['items'].items()}
    for values in scopes.values():
        for scope in values:
            scope_parts(scope)
    active = [name for name, row in rows.items() if row['status'] == 'in_progress']
    facts = coordination.load(task_dir)
    original_runs = coordination.reservations(facts)
    systemic = coordination.pending_systemic(facts)
    reserved = list(dict.fromkeys(active + [name for name in original_runs if name in rows]))
    dispatchable = []
    items = {}
    for name, row in rows.items():
        status = row['status']
        reasons = []
        conflicts = []
        classification = {'pending':'blocked', 'needs_fix':'blocked', 'in_progress':'running',
                          'blocked':'blocked', 'awaiting_verification':'awaiting_verification',
                          'verified':'terminal', 'skipped':'terminal'}[status]
        if name in errors:
            reasons.append(errors[name])
            if status == 'verified':
                classification = 'stale'
        if status in {'pending', 'needs_fix'}:
            for dep in work_items.references(definition['items'][name]['depends'], True):
                if rows[dep]['status'] != 'skipped' and (rows[dep]['status'] != 'verified' or dep in errors):
                    reasons.append(f'dependency {dep}: {errors.get(dep, rows[dep]["status"])}')
        if status == 'blocked':
            reasons.extend([row['blocked_by'], 'resume: '+row['unblock_condition']])
        if name in ready or status == 'in_progress':
            conflicts = [other for other in reserved if other != name and
                         any(overlap(a, b) for a in scopes[name] for b in scopes[other])]
            if conflicts:
                reasons.append('resource conflict: '+','.join(conflicts))
        if name in ready:
            if fields['status'] != 'in_progress':
                reasons.append('task status: '+fields['status'])
            elif systemic:
                reasons.append('pending systemic infrastructure failure; pause task before consumption')
            elif name in original_runs:
                reasons.append('original run unresolved: '+original_runs[name])
            elif not conflicts:
                classification = 'ready'
                dispatchable.append(name)
                reserved.append(name)
        items[name] = {'status':status, 'classification':classification, 'owner':row['owner'],
                       'reasons':reasons, 'conflicts':conflicts, 'scope':scopes[name]}
    return {'schema':1, 'task_id':fields['task_id'], 'task_status':fields['status'], 'ready':dispatchable,
            'running':active, 'items':items, 'completion':'Use finish/complete; frontier does not establish task completion.'}
