# Design Playbook

<stage name="design">
  <inputs>当前用户授权、contract、state、当前阶段材料。明确只读时不落盘。输入与约束先核对。</inputs>
  <procedure>## 阶段入口

适用场景：需求方向已明确，但实现边界、模块职责、数据流或方案取舍尚未定型。
输入：任务目标、研究证据、当前代码结构、约束和待决策问题。
输出：当前链路、候选方案、边界、假设、风险、验收条件和下一阶段计划。
不做什么：不修改项目代码，不把未验证的假设写成事实，不跳过用户必须确认的范围或不可逆决策。
停止条件：设计已足够支撑实施计划，或证据不足而应停在 `design_only` / `gather_more`。

1. For a new formal task, create the task skeleton and minimal contract before broad exploration, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;`. For an existing task, read the relevant code, task contract and research evidence first. Use assertion-driven local reads rather than dumping complete source files.
2. Describe the current chain, reusable capability, boundaries, assumptions and alternatives.
3. Define `objective`、`scope`、`forbidden`、`risk`、`risk_reason`、`review_policy` and numbered `Acceptance` conditions; each condition must include `outcome`、`verification`、`verification_type`、`layer` and `required`.
4. Keep `done_when` as a human-readable summary, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before moving to plan or exec.
5. Risk sets review intensity, not renewed authorization; only sensitive action categories require confirmation.
6. Write the design to `.work-docs/tasks/&lt;task-id&gt;/outputs/`.
7. Do not modify project code in the design phase.
8. If research evidence is insufficient, stop at `design_only` or `gather_more`; do not create an execution task.</procedure>
  <quality_check>同等验收下选择假设和组件更少的方案。原型仅用于回答关键未知。</quality_check>
  <exit>输出新结论或目标产物版本、证据与未覆盖项。严格 check；候选完成走 task.py complete。阻塞保留状态，不放宽必需验收。</exit>
</stage>
