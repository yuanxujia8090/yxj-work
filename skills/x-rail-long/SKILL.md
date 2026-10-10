---
name: x-rail-long
description: 跨会话、外部等待或独立依赖汇总的 x-rail 入口；保存可恢复的阶段记录。
disable-model-invocation: true
---

# x-rail-long

<skill name="x-rail-long">
  <purpose>跨会话、过夜、外部等待或独立依赖汇总时使用。多个阶段或高风险本身不触发长模式。</purpose>
  <authority source="current-user-instructions">读取 ../x-rail/SKILL.md 的公共授权规则。同范围任务复用编号。不因长模式自动委派。交接摘要不能扩权。</authority>
  <routing><reference path="../x-rail/SKILL.md" when="current-stage" />按主入口唯一阶段映射选择。小修复、单文档或普通多阶段任务保留普通模式。</routing>
  <workflow>新任务契约、状态及封存顺序引用普通入口。父契约的 Dependencies 是依赖要求唯一来源；格式 dependency: NAME|task_id=CHILD|required=yes|acceptance=A1。可选依赖 required=no 且 skip_reason 非空。状态只记录观察事实，不得删除状态行绕过依赖。audit/runs.json 保存原运行标识、提供方、工作区、观察状态和时间、输出引用，绝不保存密钥。示例见 ../x-rail/templates/long-task.md。</workflow>
  <decision_policy>确认与审查引用普通入口，不复制预算和熔断规则。依赖或授权变化须提升契约版本并记录来源，不能静默扩大 scope。</decision_policy>
  <verification>调用 python3 ../x-rail/scripts/task.py check TASK_DIR。父任务自身验收与子输出分别验证。子任务必须通过严格契约、快照、状态、证据；报告文件存在、运行返回成功或子任务自报 done 均不够。循环、自引用、重复、逃逸与缺失依赖须拒绝。</verification>
  <recovery>启动已有任务时，不创建新任务目录。先依次读取 .work-docs/index.md → contract.md → state.md → 最近 audit/checkpoint-*.md → handoff.md → audit/runs.json → 相关 evidence。核对工作区、代码版本、未提交差异和证据输入摘要。运行已完成时核对原产物，再推进父验收；不可查时记 unknown 或 blocked，不自动重发。阶段启动摘要引用普通入口。每个阶段结束都要追加一个 audit/checkpoint-序号.md，并同步更新 state.md。暂停、过夜或等待前保存 handoff。无进展、超时与基础设施失败规则只引用普通入口；不会修改全局运行配置。</recovery>
  <output_contract>交付阶段记录、真实证据、原运行引用、未满足依赖、限制与下一会话第一步。全部 required 通过才使用 complete 候选提交。blocked、stopped、cancelled 不等于完成。</output_contract>
</skill>
