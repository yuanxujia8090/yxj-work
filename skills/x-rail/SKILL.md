---
name: x-rail
description: 按交付结果分流的任务入口；按需加载执行、验证、恢复和工作项规则
disable-model-invocation: true
---

# x-rail

<skill name="x-rail">
  <purpose>先按交付结果选路径，再按失败代价和恢复需求选择普通模式或证据模式。普通任务先读、最小实施、实际验证、交付；证据模式保存契约、状态、验收证据和输入摘要。旧“严格记录/严格验证”字段保持兼容。</purpose>
  <authority source="current-user-instructions" sensitive-actions="irreversible,cost,external-publish,scope-change" readonly-no-files="true" delegation="default-active">调用本入口即授权当前目标范围内默认主动委派完整执行单元；宿主限制与用户禁止优先，短小且交接成本更高可直接完成。不扩大需求范围。不可逆、花钱、对外发布、生产变更和范围变化先确认。用户明确只读时不落盘。调用本入口不取消权限、宿主限制或必过验收；用户已批准的同范围目标跨阶段和压缩后继续。</authority>
  <routing>先按交付结果选路径，不先建记录。选择路径后读取对应 playbook；bugfix 重点是复现、根因、最小修复、回归。
    <route name="investigate" playbook="playbooks/investigate.md">现状、定位、恢复。</route>
    <route name="research" playbook="playbooks/research.md">外部事实、产品、市场、用户或技术选型研究。</route>
    <route name="design" playbook="playbooks/design.md">方案设计，不改代码。</route>
    <route name="plan" playbook="playbooks/plan.md">实施规格和轻量文档整理。</route>
    <route name="exec" playbook="playbooks/exec.md">按计划修改并验证。</route>
    <route name="bugfix" playbook="playbooks/bugfix.md">复现、根因、最小修复、回归。</route>
    <route name="review" playbook="playbooks/review.md">只读审查。</route>
    <route name="ops" playbook="playbooks/ops.md">平台操作手册；不代点网页。</route>
    <route name="mixed" playbook="playbooks/mixed.md">按当前未知组合必要阶段。</route>
    <route name="fast-answer" playbook="">简单事实、术语或命令说明；直接回答，不建任务。</route>
  </routing>
  <workflow>
    <budget L1="60" L2="150" L3="400" reminder-small="20" reminder-large="60" no-progress-minutes="30" enforcement="offline-record-consistency" />
    <recording>失败代价高、跨会话恢复、外部等待、独立审查、敏感动作、复杂跨模块实施或用户明确要求时进入证据模式；否则普通模式。证据模式使用当前工作目录 .work-docs/tasks/&lt;task-id&gt;/，保留 contract.md、state.md、evidence/、audit/ 和 outputs/。</recording>
    <loading>执行与 TDD 读取 modules/execution.md；验收、证据和输入指纹读取 modules/verification.md；中断和第三方技能读取 modules/recovery.md；工作项、依赖和委派读取 modules/work-items.md；成本授权读取 modules/cost-policy.md；持续目标、复杂定制或长期协调按需读 modules/orchestration.md。</loading>
  </workflow>
  <decision_policy>先读相关代码、说明、调用方和测试。不可逆、费用、发布和范围变化是决策门；审查不授予权限。review 按风险、覆盖不足、需求分歧、用户要求或关键逻辑重改触发。记录选择、依据和替代成本，不记录内部思考过程。</decision_policy>
  <verification>普通任务按完成条件核对预期结果。证据模式使用 task.py check/start/run/capture/record/summary/finish；每条通过验收绑定当前证据和输入摘要。命令退出 0、文件存在、编译通过或自报完成都不能单独证明完成。详细观察面、证据状态、工作项完成门见 playbooks/verification.md 和 modules/verification.md。</verification>
  <recovery>恢复读取 .work-docs/index.md、contract.md、state.md、最近 checkpoint、handoff.md、audit/ 和相关证据；核对工作区、未提交差异、输入摘要和限制。协调恢复先 task.py inbox 接收原结果、frontier 重算；原运行先查询再恢复，不原样重试；准确错误、产物和恢复第一步见 modules/recovery.md。</recovery>
  <output_contract>交付实际改动、验证输出、证据位置、未验证项、阻塞项和下一步。普通任务不制造完成文件；证据模式优先使用 task.py finish。分别报告已实现、已验证、等待授权、未验证和阻塞。</output_contract>
</skill>
