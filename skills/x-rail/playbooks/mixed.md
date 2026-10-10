# Mixed Playbook

<stage name="mixed">
  <inputs>当前用户授权、contract、state、当前阶段材料。明确只读时不落盘。输入与约束先核对。</inputs>
  <procedure>## 阶段入口

适用场景：一个任务同时包含研究、设计、实施或运维动作，且阶段之间有明确依赖。
输入：总目标、各阶段边界、研究问题、决策门和不可逆操作清单。
输出：按顺序连接的阶段产物、每阶段的完成条件、验证层级和下一阶段依赖。
不做什么：不跳过研究决策门，不把多个阶段混成一个无法验证的动作，不扩大任何子阶段范围。
停止条件：依赖链完整且每阶段独立可交接，或某个前置阶段阻塞并记录原因。

1. 先按 `research` 建立事实和 decision gate；没有 `proceed` 不进入开发阶段。
2. decision gate 为 `proceed` 时，按 `design → plan → exec → review` 继续，并把研究证据传给后续 contract。
3. decision gate 为 `design_only`、`gather_more` 或 `do_not_build` 时，在当前任务写清原因、证据和下一步，不创建没有依据的执行任务。
4. 每个阶段独立写 done_when、产物、验证层级和下一阶段依赖；阶段结束追加 checkpoint。
5. 研究结论、设计决策和执行结果都落在同一任务目录，禁止只依赖聊天上下文交接。</procedure>
  <quality_check>当前阶段独立验收，不因阶段多升级为长模式。</quality_check>
  <exit>输出新结论或目标产物版本、证据与未覆盖项。严格 check；候选完成走 task.py complete。阻塞保留状态，不放宽必需验收。</exit>
</stage>
