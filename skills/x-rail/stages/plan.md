# Plan

<stage name="plan">
  <inputs>RUN.md 的 Intent 和 Done。需要拆分的代码路径。</inputs>
  <procedure>1. 每项对应一个可验收结果；按依赖、风险和检查路径拆分。只读可共读输入，重叠写入须互斥；不按文件或单元数决定委派。
2. 依赖写进 `--deps`。有环会被 xr 拒绝。宽重构用 expand–contract：先加新路径，再切流量，最后删旧路径，拆成多个单元。
3. 命令形状：`xr plan add ID "标题" --deps none --files 输入路径 --output 独占输出路径 --verify "命令" --kind impl|review|research`。只读任务没有产物时可省略 `--output`；writer 默认把 `--files` 也作为输出范围。并留一个 `--kind integration` 收口单元。
4. 验收表至少一行：`xr acceptance set A1 "判据" --source 仓库内来源 --units 单元`。
5. 使用已授权且可用的执行者；短小且交接成本高时可直接完成。输出单写者。
6. `xr status` 能列出全部单元且依赖无环，才进入 Execute。
  <quality_check>每个单元都有 verify_cmd 和 files。没有第二个进度表。</quality_check>
  <exit>读 stages/execute.md。不要在本阶段改业务代码。</exit>
</stage>
