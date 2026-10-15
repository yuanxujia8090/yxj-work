"""Contract definitions and state rows for schema-1 work items (no separate store)."""
from __future__ import annotations

import re
from collections import Counter

IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]*')
STATUSES = {'pending', 'in_progress', 'awaiting_verification', 'needs_fix', 'blocked', 'verified', 'skipped'}
STATE_KEYS = ('status', 'owner', 'evidence_refs', 'commit', 'blocked_by', 'unblock_condition', 'reason', 'next_action')
TRANSITIONS = {
    'pending': {'in_progress', 'blocked', 'skipped'},
    'in_progress': {'awaiting_verification', 'needs_fix', 'blocked', 'skipped'},
    'awaiting_verification': {'verified', 'needs_fix', 'blocked', 'skipped'},
    'needs_fix': {'in_progress', 'blocked', 'skipped'},
    'blocked': {'pending', 'in_progress', 'awaiting_verification', 'needs_fix', 'skipped'},
    'verified': {'awaiting_verification', 'needs_fix'},
    'skipped': set(),
}


def cell(value: str) -> str:
    if not value.strip() or any(char in value for char in '\n\r|'):
        raise ValueError('work item fields must be non-empty single lines without pipes')
    return value


def references(value: str, allow_none=False, identifiers=True) -> list[str]:
    cell(value)
    if value == 'none' and allow_none:
        return []
    parts = value.split(',')
    if len(parts) != len(set(parts)) or any(not part.strip() or part != part.strip() or part == 'none' or
            (identifiers and not IDENTIFIER.fullmatch(part)) for part in parts):
        raise ValueError(f'invalid work item reference list: {value}')
    return parts


def records(lines: list[str], prefix: str, keys: set[str]) -> dict[str, dict[str, str]]:
    output = {}
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        if index + 1 < len(lines):
            following = lines[index + 1]
            if following.strip() and not following.startswith('#') and not re.match(r'^[a-z_]+:', following):
                raise ValueError(f'{prefix} record has an invalid continuation; values must use one line')
        name, *segments = line[len(prefix):].split('|')
        if not IDENTIFIER.fullmatch(name) or name == 'none':
            raise ValueError(f'invalid {prefix} identifier: {name}')
        if name in output:
            raise ValueError(f'duplicate {prefix} identifier: {name}')
        values = {}
        for segment in segments:
            if '=' not in segment:
                raise ValueError(f'malformed {prefix} record: {line}')
            key, value = segment.split('=', 1)
            if key in values or key not in keys:
                raise ValueError(f'duplicate or unknown {prefix} field: {key}')
            values[key] = cell(value)
        if set(values) != keys:
            raise ValueError(f'{prefix}{name} missing fields: {sorted(keys - set(values))}')
        output[name] = values
    return output


def definitions(lines: list[str], fields: dict, acceptances: dict) -> dict | None:
    marker = fields.get('work_items_schema')
    has_records = any(line.startswith(('requirement:', 'work_item:', 'work_items_schema:')) for line in lines)
    if marker is None:
        if has_records:
            raise ValueError('work item records require work_items_schema: 1 in contract header')
        return None
    if marker != '1':
        raise ValueError('unsupported work_items_schema; expected 1')
    requirements = records(lines, 'requirement:', {'outcome'})
    items = records(lines, 'work_item:', {'title', 'requirements', 'depends', 'scope', 'required', 'acceptances', 'skip_reason'})
    if not requirements or not items:
        raise ValueError('work_items_schema: 1 requires requirements and work items')
    covered = set()
    titles = set()
    for name, item in items.items():
        if item['title'] in titles:
            raise ValueError(f'duplicate work item title: {item["title"]}')
        titles.add(item['title'])
        reqs = references(item['requirements'])
        deps = references(item['depends'], allow_none=True)
        aids = references(item['acceptances'])
        references(item['scope'], identifiers=False)
        if set(reqs) - requirements.keys() or set(aids) - acceptances.keys() or set(deps) - items.keys():
            raise ValueError(f'unknown work item reference: {name}')
        if name in deps:
            raise ValueError(f'work item self-dependency: {name}')
        if item['required'] not in {'yes', 'no'}:
            raise ValueError(f'work item required must be yes or no: {name}')
        if item['required'] == 'no' and item['skip_reason'] == 'none':
            raise ValueError(f'optional work item needs contract skip_reason: {name}')
        covered.update(reqs)
    if covered != requirements.keys():
        raise ValueError('requirements not covered by work items')
    # Iterative topological walk avoids recursion limits for large checklists.
    remaining = set(items)
    while remaining:
        ready = {name for name in remaining if not (set(references(items[name]['depends'], True)) & remaining)}
        if not ready:
            raise ValueError('work item dependency cycle')
        remaining -= ready
    return {'requirements': requirements, 'items': items}


def state_rows(text: str, definition: dict | None, fields: dict) -> dict[str, dict[str, str]]:
    lines = text.splitlines()
    rows = records(lines, 'work_item_state:', set(STATE_KEYS))
    if definition is None:
        if rows or 'active_work_items' in fields:
            raise ValueError('work item state requires contract work_items_schema: 1')
        return rows
    if rows.keys() != definition['items'].keys():
        raise ValueError('work item state missing, extra or unknown identifiers')
    if 'active_work_items' not in fields:
        raise ValueError('missing active_work_items')
    active = references(fields['active_work_items'], True)
    if set(active) != {name for name, row in rows.items() if row['status'] == 'in_progress'}:
        raise ValueError('active_work_items differs from in_progress work items')
    for name, row in rows.items():
        item = definition['items'][name]
        if row['status'] not in STATUSES:
            raise ValueError(f'invalid work item status: {name}')
        references(row['evidence_refs'], True, identifiers=False)
        if row['reason'] == 'none' or row['next_action'] == 'none':
            raise ValueError(f'work item requires reason and next_action: {name}')
        if row['status'] == 'blocked' and (row['blocked_by'] == 'none' or row['unblock_condition'] == 'none'):
            raise ValueError(f'blocked work item needs reason and unblock_condition: {name}')
        if row['status'] == 'skipped' and (item['required'] != 'no' or item['skip_reason'] == 'none'):
            raise ValueError(f'work item cannot skip without contract reason: {name}')
        if fields.get('status') == 'done' and row['status'] not in {'verified', 'skipped'}:
            raise ValueError(f'work item not completed: {name}')
    if fields.get('status') == 'done' and active:
        raise ValueError('done task cannot have active_work_items')
    return rows


def row_text(name: str, row: dict) -> str:
    return 'work_item_state:'+name+'|'+ '|'.join(f'{key}={cell(row[key])}' for key in STATE_KEYS)+'\n'


def initial_state(definition: dict | None) -> str:
    if definition is None:
        return ''
    row = {'status': 'pending', 'owner': 'unassigned', 'evidence_refs': 'none', 'commit': 'none',
           'blocked_by': 'none', 'unblock_condition': 'none', 'reason': '尚未开始', 'next_action': '核对工作项范围与相关输入'}
    return 'active_work_items: none\n'+''.join(row_text(name, row) for name in definition['items'])


def update(text: str, definition: dict | None, fields: dict, args) -> str:
    keys = ['status', 'owner', 'evidence_ref', 'commit', 'blocked_by', 'unblock_condition', 'reason', 'next_action']
    supplied = {key: getattr(args, 'item_'+key, None) for key in keys if getattr(args, 'item_'+key, None) is not None}
    name = getattr(args, 'item', None)
    if not name:
        if supplied:
            raise ValueError('--item-* fields require --item')
        return text
    rows = state_rows(text, definition, fields)
    if definition is None or name not in rows:
        raise ValueError(f'unknown work item: {name}')
    if not supplied.get('reason') or not supplied.get('next_action'):
        raise ValueError('work item update requires --item-reason and --item-next-action')
    old = rows[name]
    new = old.copy()
    for key, value in supplied.items():
        assert value is not None
        if key == 'evidence_ref':
            if 'none' in value and value != ['none']:
                raise ValueError('none cannot be mixed with evidence references')
            if any(',' in ref for ref in value):
                raise ValueError('use repeated --item-evidence-ref; each path cannot contain a comma')
            new['evidence_refs'] = ','.join(cell(ref) for ref in value)
        else:
            new[key] = cell(value)
    if new['status'] != old['status'] and new['status'] not in TRANSITIONS[old['status']]:
        raise ValueError(f'invalid work item transition: {old["status"]} -> {new["status"]}')
    if new['status'] == 'skipped' and definition['items'][name]['required'] != 'no':
        raise ValueError('required work item cannot be skipped')
    rows[name] = new
    text = re.sub(r'^work_item_state:'+re.escape(name)+r'\|.*\n?', lambda _: row_text(name, new), text, flags=re.M)
    active = ','.join(name for name, row in rows.items() if row['status'] == 'in_progress') or 'none'
    return re.sub(r'^active_work_items: .*$', lambda _: 'active_work_items: '+active, text, flags=re.M)


def summary(definition: dict | None, rows: dict, validity) -> list[str]:
    if definition is None:
        return ['工作项：旧格式，未采用逐项检查']
    counts = Counter(row['status'] for row in rows.values())
    output = [f'需求覆盖：{len(definition["requirements"])}/{len(definition["requirements"])}',
              '工作项计数：'+', '.join(f'{status}={counts[status]}' for status in sorted(STATUSES))]
    valid = {}
    for name, row in rows.items():
        detail = ''
        if row['status'] == 'verified':
            try:
                validity(name)
                valid[name] = True
            except (OSError, ValueError) as error:
                detail = f'；stale/invalid：{error}'
        if row['status'] == 'skipped':
            detail = f'；契约跳过理由：{definition["items"][name]["skip_reason"]}'
        output.append(f'{name}: {row["status"]}；{definition["items"][name]["title"]}；执行者：{row["owner"]}'
                      f'；证据：{row["evidence_refs"]}；阻塞：{row["blocked_by"]}；解除条件：{row["unblock_condition"]}'
                      f'；原因：{row["reason"]}；下一步：{row["next_action"]}{detail}')
    ready = [name for name, row in rows.items() if row['status'] in {'pending', 'needs_fix'} and
             all(valid.get(dep) or rows[dep]['status'] == 'skipped' for dep in references(definition['items'][name]['depends'], True))]
    output.append('可执行候选：'+(','.join(ready) or 'none'))
    return output
