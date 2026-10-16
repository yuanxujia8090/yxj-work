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
assert '相互独立、无共享写入、无前置依赖' in core_text
assert '预计超过 8KB' in core_text
assert '原始输出' in core_text
assert '通过数量' in core_text
assert '失败测试名' in core_text
verification_text=(root/'skills/x-rail/playbooks/verification.md').read_text()
for path in ['README.md', 'docs/architecture.md', 'docs/usage-guide.html']:
    doc=(root/path).read_text()
    assert '预计超过 8KB' in doc, path
    assert '相互独立、无共享写入、无前置依赖' in doc, path
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
# 子代理运行时限由宿主配置，不从任务预算或记录期限推导覆盖参数。
work_items_text=core.find('workflow/work_items').text
child_text=(root/'skills/x-rail/templates/child-task.md').read_text()
for text in [work_items_text, child_text]:
    for rule in ['子代理总时限沿用宿主与代理配置', '默认省略 timeoutMs/maxRuntimeMs',
                 '不在提示词或子任务停止条件中另设运行倒计时',
                 '仅当前用户明确要求或更高优先级规则强制时传入', '并记录来源',
                 '任务记录总期限、无进展阈值和单条验证命令超时不转换成子代理总时限']:
        assert rule in text, rule
assert '到期前保存状态' not in child_text
assert '到期交付' not in child_text
# 仅检查规则表达与引用；不代表模型已遵守主动委派或真实接力已验证。
exec_text=(root/'skills/x-rail/playbooks/exec.md').read_text()
exec_procedure=m.parse_body(exec_text,'exec').find('procedure').text
rule_groups={
    '先定结果': ['最小相关材料与调用方', '暂停扩大改动', '保留已有修改和有效证据'],
    '主动交接': ['默认将完整执行单元交给子代理', '有依赖项在前置满足后接力',
                 '交接成本明显更高时直接完成', '紧密耦合的实现由同一位执行者承接'],
    '隔离写入': ['父状态、分支、数据库、缓存和构建目录', '核对宿主实际模式', '原运行先查询再恢复'],
    '精简返回': ['实际修改位置与版本', '后继必要约定', '关键失败与限制不能省略', '安全节点'],
    '按缺口核验': ['仍适用的检查直接复用', '接入实际交付工作区', '中高风险和契约必需独立审查'],
    '达到验收就交付': ['观察对象、必要检查与结束条件', '不默认叠加多轮全量审查', '既有必需最终审查']
}
for name, rules in rule_groups.items():
    assert f'**{name}。**' in exec_procedure, name
    for rule in rules:
        assert rule in exec_procedure, (name, rule)
assert '完整执行单元' in work_items_text and '接力' in work_items_text
assert 'playbooks/exec.md' in work_items_text
assert '使用子代理或任务内部存在先后关系，本身不触发长模式' in core_text
for rule in ['../playbooks/exec.md', '完整执行单元', '可访问', '实际修改位置与版本', '偏差']:
    assert rule in child_text, ('child-task', rule)
for path in ['README.md', 'docs/architecture.md', 'docs/usage-guide.html']:
    doc=(root/path).read_text()
    assert '子代理总时限沿用宿主与代理配置' in doc, path
    assert 'timeoutMs/maxRuntimeMs' in doc, path
# 对外说明与冲突处引用同一委派规则；关键词通过不等于真实接力已发生。
stale_parallel=('优先子代理并行实现', '优先交子代理并行实现', '优先由子代理并行实现', '优先并行')
aligned=('README.md', 'docs/architecture.md', 'docs/usage-guide.html', 'skills/x-rail/playbooks/plan.md')
for path in aligned:
    doc=(root/path).read_text()
    for rule in ('完整执行单元', '有依赖项在前置满足后接力', '交接成本明显更高时直接完成'):
        assert rule in doc, (path, rule)
    assert not any(phrase in doc for phrase in stale_parallel), path
for path in ('skills/x-rail/playbooks/verification.md', 'skills/x-rail/templates/document-task.md'):
    doc=(root/path).read_text()
    assert 'exec.md' in doc, path
    assert '不能从拆分推导委派权' in doc, path
    assert not any(phrase in doc for phrase in stale_parallel), path
# 4.6 不再把实现默认留给主会话；代码审查说明仍保留该句。
guide=(root/'docs/usage-guide.html').read_text()
boundary=guide.split('id="skillrule"',1)[1].split('id="light-document"',1)[0]
assert '默认由主会话直接执行' not in boundary
assert '逐项更新与执行交接' in boundary
review=guide.split('x-requesting-code-review',1)[1].split('x-receiving-code-review',1)[0]
assert '默认由主会话直接执行' in review
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
print('test-flow: passed (6 static rule groups, semantic modules, 10 routes, readonly, authorization, conditional references, recovery)')
PY
