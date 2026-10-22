# Execute

<stage name="execute">
  <inputs>units.tsv、capsule.md、当前集成分支。</inputs>
  <procedure>1. 循环：`xr next`。没有可执行单元就去 Review；阻塞项先核对原因和原运行，不释放未解决范围。
2. 由获授权且掌握材料的执行者完成单元；短小项可由主会话做。行为改动用 Skill 工具 tdd，bug 用 diagnosing-bugs；seam 用 `xr decide` 记录。
3. 并发遵守宿主限制。只读任务可共读输入，重叠写入和报告输出须互斥。
4. 网络、工具或未知故障用 `xr fail ID --kind TYPE --record REF` 保存错误、原运行及已有结果并阻塞，禁止自动重派。核实原运行后用 `xr reopen ID --resolution resumed|terminated --record REF`；活跃则续同一运行，沿原单元验证并完成；终止才接收结果并规划剩余项；未知保持阻塞。缺报告不阻止已确认终止后的重规划，但不可声称覆盖已复用。
5. 决策门解除不解除其他阻塞；门暂停的 doing 项仍占用原范围，须核实原运行后恢复。
6. 合并由主会话串行完成；随后 `xr verify`，通过才 `xr done`。文档/研究/人工核对类用 `--verify-kind observation` 并按 references/verification.md 落观察证据，不伪造 `--verify "true"`。冲突大就拆新单元。单元完成后由 x-run-guard 决定继续、委派或压缩。</procedure>
  <quality_check>存在写入的重叠单元互斥；阻塞但原运行状态未知的写入范围仍占用。每个 done 都有 VERIFIED。</quality_check>
  <exit>frontier 空或预算到 70%：读 stages/review.md 或 stages/land.md。</exit>
</stage>
