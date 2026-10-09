#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# Caller may contain all test artifacts inside its task directory.
tmp="$(mktemp -d "${TMPDIR:-/tmp}/document-template.XXXXXX")"
TEMPLATE="$ROOT/skills/x-rail/templates/document-task.md"
[[ -f "$TEMPLATE" ]] || { printf 'document-template: missing template\n' >&2; exit 1; }
python3 - "$TEMPLATE" "$tmp" <<'PY'
import sys, pathlib, re, hashlib, datetime
source = pathlib.Path(sys.argv[1]).read_text()
task = pathlib.Path(sys.argv[2]) / '20261008-01-template-check'
for name in ['outputs', 'evidence', 'audit', 'tmp']:
    (task / name).mkdir(parents=True, exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
for name in ['coverage', 'clarity']:
    (task / f'evidence/{name}.txt').write_text('not_run: not checked yet\n')
values = {'TASK_ID': task.name, 'OBJECTIVE': '整理测试用例', 'SOURCES': '方案.md；固定提交 abc123',
          'DELIVERABLE': 'test-cases.md', 'NOW': now}
for name in ['contract.md', 'state.md']:
    match = re.search(r'### ' + re.escape(name) + r'\n\n```text\n(.*?)\n```', source, re.S)
    assert match, f'missing block {name}'
    text = match.group(1) + '\n'
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    if name == 'state.md':
        text = text.replace('{{CONTRACT_SHA256}}', hashlib.sha256((task/'contract.md').read_bytes()).hexdigest())
    assert not re.search(r'\{\{.*?\}\}', text), 'unfilled template token'
    (task / name).write_text(text)
print(task)
PY
task="$tmp/20261008-01-template-check"
bash "$ROOT/skills/x-rail/scripts/check-contract.sh" "$task"
bash "$ROOT/skills/x-rail/scripts/check-state.sh" "$task"
# A copied, unfinished template must NOT be accepted as done.
python3 - "$task/state.md" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); p.write_text(p.read_text().replace('status: in_progress', 'status: done'))
PY
if result="$(bash "$ROOT/skills/x-rail/scripts/check-state.sh" "$task" 2>&1)"; then
  printf 'document-template: unfinished document accepted as done\n' >&2; exit 1
fi
[[ "$result" == *'required acceptance not passed'* ]] || { printf '%s\n' "$result"; exit 1; }
# Genuine completion binds two distinct checks; no website execution is claimed.
python3 - "$task" <<'PY'
import sys, pathlib, datetime
p = pathlib.Path(sys.argv[1]); now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
(p/'outputs/test-cases.md').write_text('场景：仅联系人不得进入后台。前置：联系人账号。操作：登录。预期：无站点权限。依据：方案第1条。测试未执行。\n')
s = (p/'state.md').read_text()
for n, name in [(1, 'coverage'), (2, 'clarity')]:
    (p/f'evidence/{name}.txt').write_text(f'checked actual fixture document for acceptance A{n}; passed\n')
    s = s.replace(f'A{n} status=not_run', f'A{n} status=passed')
    s = s.replace(f'evidence:{name}|acceptance=A{n}|command=not_run', f'evidence:{name}|acceptance=A{n}|command=review actual fixture document')
s = s.replace('|result=not_run|', '|result=passed|')
(p/'state.md').write_text(s)
PY
bash "$ROOT/skills/x-rail/scripts/check-state.sh" "$task"
# Template must ship unmodified in a temporary copy install.
bash "$ROOT/scripts/install.sh" --dest "$tmp/installed" >/dev/null
cmp "$TEMPLATE" "$tmp/installed/x-rail/templates/document-task.md"
printf 'document-template: passed (initial state, unfinished done rejected, verified done, installed template)\n'
