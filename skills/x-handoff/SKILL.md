---
name: x-handoff
description: 将当前任务的真实状态和恢复第一步写入授权的 handoff.md。
disable-model-invocation: true
---

# x-handoff

<skill name="x-handoff">
  <purpose>用户明确调用时保存当前任务交接，不创建新的执行任务。</purpose>
  <authority source="current-user-instructions">只能由用户主动调用。仅写当前 .work-docs/tasks/TASK_ID/handoff.md。交接不改变 contract 与当前用户授权，也不覆盖其他任务。</authority>
  <routing>阶段与授权引用 ../x-rail/SKILL.md；跨会话恢复引用 ../x-rail-long/SKILL.md。</routing>
  <workflow>读取索引 → contract → state → 最近 checkpoint → handoff → audit/runs.json → 相关证据。核对目录、分支、提交、未提交差异、输入摘要和原运行。过期证据须重新实际验证，不能因时间较新就跳过输入核对。</workflow>
  <decision_policy>范围冲突以契约和当前用户授权为准。依赖、费用或发布未获授权保持阻塞；摘要不授予权限。</decision_policy>
  <verification>运行严格 task.py check，只读核对状态。历史材料只能显式历史模式读取，不伪造过去快照。交接不是完成证明。</verification>
  <recovery>优先查询原运行；未知或不可查询时记录阻塞，不新派、不原样重试、不切运行协议。保存准确错误、失败策略及解除条件。</recovery>
  <output_contract>写背景、目标、阶段、状态、已完成、未完成、实际验证输出、证据、运行引用、约束、待授权、最近 checkpoint、next_action。末尾“下一会话第一步”与 next_action 第一条一致。新会话先核对事实再执行。</output_contract>
</skill>
