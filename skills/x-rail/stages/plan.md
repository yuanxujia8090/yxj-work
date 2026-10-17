# Plan

<stage name="plan">
  <inputs>RUN.md 的 Intent 和 Done。需要拆分的代码路径。</inputs>
  <procedure>1. 每个单元竖切：单独能验证，有一条 verify_cmd，一个独占 `--files`。预计不超过 40 轮、150K 上下文。
2. 依赖写进 `--deps`。有环会被 xr 拒绝。宽重构用 expand–contract：先加新路径，再切流量，最后删旧路径，拆成多个单元。
3. 命令形状：`xr plan add ID "标题" --deps none --files 路径 --verify "命令" --kind impl|review|research`。
4. 数单元。少于 5 个：mode 保持 main，主会话写代码。达到 5 个：xr 记「走子代理」。用户在 RUN.md 写 `mode: main` 或 `mode: subagents` 可以覆盖。
5. 共享文件（锁、路由、全局配置）归进一个集成单元，不并行。
6. 可选试点：先做第一个单元，用它校正时间盒，再铺开。
7. `xr status` 能列出全部单元且依赖无环，才进入 Execute。</procedure>
  <quality_check>每个单元都有 verify_cmd 和 files。没有第二个进度表。</quality_check>
  <exit>读 stages/execute.md。不要在本阶段改业务代码。</exit>
</stage>
