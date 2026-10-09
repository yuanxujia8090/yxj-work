# Research Playbook

## 阶段入口

适用场景：需要收集外部事实、产品信息、市场信息、用户信息或技术选型依据。
输入：研究对象、版本/环境边界、需要回答的问题和可接受的事实来源。
输出：证据账本、事实与推断的区分、未知项、矛盾记录和 decision gate（决策门）结论。
不做什么：不把搜索摘要当作事实，不在 `proceed` 之前进入设计、计划或实施，不替用户拍板不可逆决策。
停止条件：得到 `proceed`、`design_only`、`gather_more` 或 `do_not_build` 中一个有证据的结论。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh <task-dir>` before broad exploration. For an existing task, first read its contract and state. If a model request times out, record a recovery summary in `audit/` before continuing.
2. Confirm object, terminology, version and environment; unresolved identity blocks conclusions.
3. Rewrite the request as a falsifiable question with done_when and stop_when; split into 1–5 claims.
4. Prefer official documentation/API, official repositories/releases, primary data or user statements, reproducible measurements, then secondary sources.
5. Keep an evidence ledger with `claim`, `source`, `date`, `fact_or_inference`, `confidence`, `reproducible`, `contradiction`, and `scope`.
5. Separate facts, inferences and unknowns. Record failed paths and why they do not prove the claim.
6. Run a minimal measurement only when it can change the decision. Distinguish structure/configuration success from credential, permission, rate-limit and external-service failure.
7. Write the final report to `.work-docs/tasks/<task-id>/outputs/`; write ledger and run records to `evidence/` or `audit/`.
8. End with `decision_gate: proceed|design_only|gather_more|do_not_build` and a development handoff containing scope, evidence pointers, acceptance direction and irreversible decisions still requiring a human.
