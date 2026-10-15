#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" <<'PY'
import importlib.util,pathlib,sys,xml.etree.ElementTree as E
root=pathlib.Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('xml',root/'scripts/check-skill-xml.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
result=m.check_root(root)
core_text=(root/'skills/x-rail/SKILL.md').read_text()
core=m.parse_body(core_text,'core')
authority=core.find('authority')
assert 'failure_cost_high' in core_text
assert 'recovery_or_handoff_needed' in core_text
assert '任一为真' in core_text
assert '任务名称' in core_text
assert '最短路径' in core_text
assert '不要求默认完整链路' in core_text
assert '按风险触发' in core_text
verification_text=(root/'skills/x-rail/playbooks/verification.md').read_text()
assert '输入集合由执行者声明' in verification_text
assert '文本包含关系不能证明完整行为' in verification_text
assert authority.get('readonly-no-files')=='true'
assert authority.get('delegation')=='explicit-only'
assert authority.get('sensitive-actions')=='irreversible,cost,external-publish,scope-change'
cost_policy=core.find('workflow/cost_policy')
assert cost_policy is not None
for rule in ['解除成本限制','不限制成本','不要解除成本限制','解除阻塞','cost_control: unlimited','cost_authorization:','跨会话恢复','无进展','硬限制']:
    assert rule in cost_policy.text, rule
for path in ['skills/x-rail/playbooks/plan.md','skills/x-rail/templates/child-task.md','skills/x-rail/templates/document-task.md']:
    assert '不限成本' in (root/path).read_text(), path
assert 'budget: unlimited' in verification_text
for stage in result['routes']:
    if stage=='fast-answer':continue
    tree=m.parse_body((root/f'skills/x-rail/playbooks/{stage}.md').read_text(),stage)
    assert all((tree.find(name).text or '').strip() for name in m.STAGE_MODULES)
    procedure=tree.find('procedure').text
    for field in ['适用场景：','输入：','输出：','不做什么：','停止条件：']:assert field in procedure,(stage,field)
refs=core.findall('routing/route[@name="exec"]/reference')
assert all(r.get('when')!='always' for r in refs)
assert any(r.get('when')=='typescript-project-rules-insufficient' for r in refs)
for stage in ['plan','design','review','bugfix','exec']:
    tree=m.parse_body((root/f'skills/x-rail/playbooks/{stage}.md').read_text(),stage)
    assert tree.find('quality_check').text
long=m.parse_body((root/'skills/x-rail-long/SKILL.md').read_text(),'long')
assert 'contract.md' in long.find('recovery').text and 'audit/runs.json' in long.find('recovery').text
handoff=m.parse_body((root/'skills/x-handoff/SKILL.md').read_text(),'handoff')
assert '下一会话第一步' in handoff.find('output_contract').text
assert (root/'skills/x-rail/templates/child-task.md').is_file()
assert (root/'skills/x-rail/templates/long-task.md').is_file()
assert (root/'skills/x-self-check/scripts/analyze_sessions.py').is_file()
print('test-flow: passed (semantic modules, 10 routes, readonly, authorization, conditional references, recovery)')
PY
