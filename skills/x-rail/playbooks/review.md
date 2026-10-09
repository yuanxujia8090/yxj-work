# Review Playbook

## 阶段入口

适用场景：已有代码或文档变更，需要在交付前检查需求符合度、正确性、安全边界和完成证据。
输入：contract、变更集、原始需求、已有证据、未验证项和相关局部实现。
输出：按风险排序的问题、证据位置、未覆盖范围、审查结论和与策略匹配的 review evidence。
不做什么：不把测试全绿当作无缺陷，不越过用户确认门，不在只读审查中修改目标文件。
停止条件：每条 Acceptance 都有对应审查结论和证据，或明确列出阻塞与未审查范围。

1. Read the contract, change set, evidence and unverified items. For a new formal task, create the task skeleton and minimal contract before broad exploration. If a model request times out, record the recovery summary in `audit/` before continuing.
2. Run `skills/x-rail/scripts/check-contract.sh <task-dir>` for a v2 contract before reviewing the change set.
3. Apply the contract's `review_policy`: low/auto uses automatic verification plus a delivery summary; medium/user-confirm adds an independent read-only review; high/full-review requires user confirmation and full review.
   For `review_policy: auto` + low-risk + read-only reviews, use **轻量 review**: keep contract, evidence, state and both check scripts; skip builds, tests and unrelated reference files unless an Acceptance condition requires them.
4. 先列断言，再按断言读取局部实现。Start with an assertion ledger: list the document/spec claims or Acceptance conditions, map each to implementation symbols, read only the relevant local code, and write evidence immediately. Do not dump multiple complete source files before identifying the claim they answer.
5. Review correctness, security boundaries, maintainability, completion-condition coverage and workflow file boundary.
6. Confirm each numbered `Acceptance` condition has the declared evidence type and layer; do not treat a manual, consumer or external condition as passed from a local command alone.
7. Classify findings as must-fix, consider, note or rejected; cite files and evidence.
8. State what was not reviewed.
9. Write the review result to the contract's `review_evidence` path under `.work-docs/tasks/<task-id>/`; the state must record matching `policy` and `status=passed` before `done`.
10. This playbook is read-only. Put the review in `.work-docs/tasks/<task-id>/outputs/` only when requested by the contract.
