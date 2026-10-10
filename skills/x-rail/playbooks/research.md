# Research Playbook

<stage name="research">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；下面的 contract/state、初始化、evidence/audit 和候选要求只适用于严格记录。用户授权的目标文档写指定位置。

适用场景：需要收集外部事实、产品信息、市场信息、用户信息或技术选型依据。
输入：研究对象、版本/环境边界、需要回答的问题和可接受的事实来源。
输出：证据账本、事实与推断的区分、未知项、矛盾记录和 decision gate（决策门）结论。
不做什么：不把搜索摘要当作事实，不在 `proceed` 之前进入设计、计划或实施，不替用户拍板不可逆决策。
停止条件：得到 `proceed`、`design_only`、`gather_more` 或 `do_not_build` 中一个有证据的结论。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before broad exploration. For an existing task, first read its contract and state. If a model request times out, record a recovery summary in `audit/` before continuing.
2. Confirm object, terminology, version and environment; unresolved identity blocks conclusions.
3. Rewrite the request as a falsifiable question with done_when and stop_when; split into 1–5 claims.
4. Prefer official documentation/API, official repositories/releases, primary data or user statements, reproducible measurements, then secondary sources.
5. Keep an evidence ledger with `claim`, `source`, `date`, `fact_or_inference`, `confidence`, `reproducible`, `contradiction`, and `scope`.
5. Separate facts, inferences and unknowns. Record failed paths and why they do not prove the claim.
6. Run a minimal measurement only when it can change the decision. Distinguish structure/configuration success from credential, permission, rate-limit and external-service failure.
7. Write the final report to `.work-docs/tasks/&lt;task-id&gt;/outputs/`; write ledger and run records to `evidence/` or `audit/`.
8. End with `decision_gate: proceed|design_only|gather_more|do_not_build` and a development handoff containing scope, evidence pointers, acceptance direction and irreversible decisions still requiring a human.</procedure>
  <quality_check>事实、推断、假设分开，定向补读关键缺口，不无界调查。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
