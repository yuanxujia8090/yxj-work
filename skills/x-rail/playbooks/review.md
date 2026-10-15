# Review Playbook

<stage name="review">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；严格任务才读取 contract/state 并保留 evidence/audit。用户授权的目标文档写指定位置。公共生命周期规则以主入口为准。

适用场景：已有代码或文档变更，需要在交付前检查需求符合度、正确性、安全边界和完成证据。
输入：contract、变更集、原始需求、已有证据、未验证项和相关局部实现。
输出：按风险排序的问题、证据位置、未覆盖范围、审查结论和与策略匹配的 review evidence。
不做什么：不把测试全绿当作无缺陷，不越过用户确认门，不在只读审查中修改目标文件。
停止条件：每条 Acceptance 都有对应审查结论和证据，或明确列出阻塞与未审查范围。

1. Read the contract, change set, evidence and unverified items. 先核对原任务结果 → 原始证据 → 当前相关输入 → 验证环境、时间和限制，再决定重跑。更换会话本身不使证据失效；相关输入、外部环境或时效要求变化时，只重跑受影响检查。当前环境缺失不能证明过去未验证。可用 task.py summary 生成只读摘要，但摘要不代替原证据与独立判断。For a new formal task, create the task skeleton and minimal contract before broad exploration. If a model request times out, record the recovery summary in `audit/` before continuing.
2. Run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` for a v2 contract before reviewing the change set.
3. Apply the contract's `review_policy`: low/auto uses automatic verification plus a delivery summary; medium/user-confirm adds an independent read-only review; high/full-review requires full review; confirmation depends on sensitive actions.
   低风险只读审查默认普通流程，直接交付问题、依据和未覆盖范围，不建任务文件。已有严格契约时保留 contract/evidence/state；只运行验收要求的检查，不重复独立审查。
4. 先列断言，再按断言读取局部实现。Start with an assertion ledger: list the document/spec claims or Acceptance conditions, map each to implementation symbols, read only the relevant local code, and write evidence immediately. Do not dump multiple complete source files before identifying the claim they answer.
5. Review correctness, security boundaries, maintainability, completion-condition coverage and workflow file boundary. 使用 work_items_schema: 1 时逐项核对需求覆盖、文件范围、依赖、实际产物与验收引用；工作项 verified 或子代理通知不能代替当前有效证据。整体状态与七种工作项状态分开，不能通过改清单规避未完成项。
6. Confirm each numbered `Acceptance` condition has the declared evidence type and layer; do not treat a manual, consumer or external condition as passed from a local command alone.
7. Classify findings as must-fix, consider, note or rejected; cite files and evidence.
8. State what was not reviewed. 固定本批输入，集中交回必修问题及其影响项，供执行者集中修复后重跑受影响检查。优先恢复原审查运行定向复核；不可恢复时记录原因并按宿主规则建立同角色替代。原审查复核不能替代契约要求的独立最终审查，必修项不能降成可选。非阻塞建议写现有决定或后续事项，不无限扩展收口范围。
   修复相关代码或报告后重新核对对应输入与证据；无关文件变化不自动使全部证据失效。范围按实际调用和验收确定，不能缩小输入声明逃避重审；state.md 不作为代码审查输入，避免记进度使证据自我失效。基础设施错误立即报告并暂停依赖，保存准确错误、原运行、目录和已有产物；不换协议、不重复启动、不以主会话自查冒充独立审查。审查返回和修复验证结果由唯一状态写入者更新工作项，审查者保持只读。
9. Write the review result to the contract's `review_evidence` path under `.work-docs/tasks/&lt;task-id&gt;/`; the state must record matching `policy` and `status=passed` before `done`.
10. This playbook is read-only. Put the review in `.work-docs/tasks/&lt;task-id&gt;/outputs/` only when requested by the contract.</procedure>
  <quality_check>有限问题与证据包判断，证据不足逐题拒绝推断。运行成功、输出非空、验收通过分开。独立审查无授权则 blocked，不冒充。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
