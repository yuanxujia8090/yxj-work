# Mixed Playbook

1. 先按 `research` 建立事实和 decision gate；没有 `proceed` 不进入开发阶段。
2. decision gate 为 `proceed` 时，按 `design → plan → exec → review` 继续，并把研究证据传给后续 contract。
3. decision gate 为 `design_only`、`gather_more` 或 `do_not_build` 时，在当前任务写清原因、证据和下一步，不创建没有依据的执行任务。
4. 每个阶段独立写 done_when、产物、验证层级和下一阶段依赖；阶段结束追加 checkpoint。
5. 研究结论、设计决策和执行结果都落在同一任务目录，禁止只依赖聊天上下文交接。
