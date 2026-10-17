---
name: x-rail-long
description: 跨会话、外部等待或独立依赖汇总的 x-rail 入口；保存可恢复的阶段记录。
disable-model-invocation: true
---

# x-rail-long

<skill name="x-rail-long">
  <purpose>跨会话、过夜、外部等待或独立依赖汇总时使用。多个阶段或高风险本身不触发长模式。</purpose>
  <authority source="current-user-instructions">读取 ../x-rail/SKILL.md 的公共授权规则。调用 x-rail-long 即优先使用子代理承接当前目标范围内完整执行单元；依赖串行接力、共享写由同一子代理承接，不把不可并行或文件共享当父包办理由。短小且交接成本明显更高时可父直接完成。该授权不代表无限成本、新购买、生产、不可逆、发布或范围变更；用户禁止、更高规则与宿主限制优先。交接摘要不能扩权。</authority>
  <routing><reference path="../x-rail/SKILL.md" when="current-stage" />先按主入口交付结果分流，再选择阶段。实际需要跨会话、外部等待或依赖汇总才保留长模式；当前会话能完成的小修复、单文档或普通多阶段任务退回普通流程。</routing>
  <workflow>长模式使用严格记录。新任务写契约后优先 task.py start 生成状态并封存，完成优先 finish；已有任务续接，不重建。公共顺序引用主入口。父契约的 Dependencies 是依赖要求唯一来源；格式 dependency: NAME|task_id=CHILD|required=yes|acceptance=A1。可选依赖 required=no 且 skip_reason 非空。状态只记录观察事实，不得删除状态行绕过依赖。audit/runs.json 保存原运行标识、提供方、工作区、观察状态和时间、输出引用，绝不保存密钥。示例见 ../x-rail/templates/long-task.md。</workflow>
  <decision_policy>确认与审查引用普通入口，不复制预算和熔断规则。依赖或授权变化须提升契约版本并记录来源，不能静默扩大 scope。</decision_policy>
  <verification>调用 python3 ../x-rail/scripts/task.py check TASK_DIR。父任务自身验收与子输出分别验证。子任务必须通过严格契约、快照、状态、证据；报告文件存在、运行返回成功或子任务自报 done 均不够。循环、自引用、重复、逃逸与缺失依赖须拒绝。</verification>
  <recovery>启动已有任务时，不创建新任务目录。先依次读取 .work-docs/index.md → contract.md → state.md → 最近 audit/checkpoint-*.md → handoff.md → audit/runs.json → 相关 evidence。核对工作区、代码版本、未提交差异和证据输入摘要。运行已完成时核对原产物，再推进父验收；不可查时记 unknown 或 blocked，不自动重发。阶段启动摘要引用普通入口。只在重要决定、验证、转向、阻塞、交接或交付时保存必要变化，阶段变化影响恢复时随之更新；不为每个阶段重复追加相同事实。协调原运行、通知与消费用 task.py dispatch/notify/inbox/consume；恢复先列 inbox，再 frontier 重算，不启动新运行绕过原现场。完整循环见 ../x-rail/modules/orchestration.md。进度、阻塞和恢复用 task.py update，摘要用 summary；仅更新时间不算进展，真实新结论才用 --progress 并说明原因。证据因相关输入、外部环境或时效要求变化而需复验；换会话本身不使其失效。暂停、过夜或等待前保存恢复第一步和易错点，其他事实引用原记录。无进展、超时与基础设施失败规则只引用普通入口；不会修改全局运行配置。</recovery>
  <output_contract>交付阶段记录、真实证据、原运行引用、未满足依赖、限制与下一会话第一步。全部 required 通过才使用 complete 候选提交。blocked、stopped、cancelled 不等于完成。</output_contract>
</skill>
