#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/document-template.XXXXXX")"
PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" "$tmp" <<'PY'
import datetime, hashlib, json, pathlib, re, subprocess, sys
root, temp = map(pathlib.Path, sys.argv[1:])
source = (root/'skills/x-rail/templates/document-task.md').read_text()
task = temp/'.work-docs/tasks/20261010-01-template'
for name in ['outputs','evidence','audit']: (task/name).mkdir(parents=True,exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
values = {'TASK_ID': task.name, 'OBJECTIVE': '整理用例', 'SOURCES': 'fixed-design.md', 'DELIVERABLE': 'test-cases.md', 'NOW': now}
for name in ['contract.md','state.md']:
    text = re.search(r'### '+re.escape(name)+r'\n\n```text\n(.*?)\n```', source, re.S).group(1)+'\n'
    for key,value in values.items(): text=text.replace('{{'+key+'}}',value)
    if name=='state.md': text=text.replace('{{CONTRACT_SHA256}}',hashlib.sha256((task/'contract.md').read_bytes()).hexdigest())
    assert '{{' not in text
    (task/name).write_text(text)
cli = root/'skills/x-rail/scripts/task.py'
def run(*args, good=True):
    p=subprocess.run([sys.executable,str(cli),*map(str,args)],capture_output=True,text=True)
    assert (p.returncode==0)==good, p.stdout+p.stderr
    return p
run('seal',task); run('check',task)
original=(task/'state.md').read_bytes()
candidate=task/'candidate.md'; candidate.write_text(original.decode().replace('status: in_progress','status: done'))
run('complete',task,'--candidate',candidate,good=False)
assert (task/'state.md').read_bytes()==original
(temp/'fixed-design.md').write_text('联系人不授权。')
(task/'outputs/test-cases.md').write_text('场景：联系人登录。前置：仅联系人。操作：登录。预期：无权限。依据：fixed-design。测试未执行。')
state=original.decode().replace('status: in_progress','status: done')
for i,name in [(1,'coverage'),(2,'clarity')]:
    (task/f'evidence/{name}.txt').write_text(f'实际材料与交付逐项核对 A{i}：passed')
    data={'version':1,'contract_revision':1,'workspace_root':str(temp.resolve()),'files':[{'path':str(p.relative_to(temp)),'state':'present','sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [temp/'fixed-design.md',task/'outputs/test-cases.md']]}
    (task/f'evidence/{name}.inputs.json').write_text(json.dumps(data))
    state=state.replace(f'A{i} status=not_run',f'A{i} status=passed evidence=evidence/{name}.txt')
    state+=f'evidence:{name}|acceptance=A{i}|command=人工核对实际文档|run_at={now}|result=passed|last_edit_at={now}|inputs=evidence/{name}.inputs.json|contract_revision=1\n'
candidate.write_text(state); run('complete',task,'--candidate',candidate); run('check',task)
print('document-template: passed (sealed initial, unfinished rejected without mutation, bound candidate completed)')
PY
bash "$ROOT/scripts/install.sh" --dest "$tmp/installed" >/dev/null
cmp "$ROOT/skills/x-rail/templates/document-task.md" "$tmp/installed/x-rail/templates/document-task.md"
mkdir "$tmp/consumer"
(cd "$tmp/consumer" && PYTHONDONTWRITEBYTECODE=1 python3 "$tmp/installed/x-rail/scripts/task.py" check "$tmp/.work-docs/tasks/20261010-01-template")
printf 'document-template: installed consumer passed; artifacts=%s\n' "$tmp"
