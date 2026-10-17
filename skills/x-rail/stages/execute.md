# Execute

<stage name="execute">
  <inputs>units.tsv、capsule.md、当前集成分支。</inputs>
  <procedure>1. 循环：`xr next`。没有单元就去 Review。墙钟到 70% 就停止开新单元，去 Land。
2. 少于 5 个单元：主会话做当前 doing 单元。行为改动调用 Skill 工具 tdd，seam 用 `xr decide` 记下。bug 调用 Skill 工具 diagnosing-bugs，先有变红的命令。
3. 达到 5 个单元：主会话只编排。每个 impl 单元一个 worker，Brief 用 references/brief-template.md。worktree 用 x-worktree，分支 xr/run/unit，从集成分支最新提交拉出。
4. 并发：只读（research、review）最多 5，写入最多 2，合计最多 5。熔断打开时合计 2、写入 1。`xr next` 会拒绝重叠文件和超额。
5. 软 30 分钟：worker 把进度写到 notes/单元-report.md 并提交 wip。快完成就让它跑到硬超时 45 分钟；否则 `xr fail ID --kind cap` 再拆小。reviewer 硬 25 分钟，researcher 和 scout 硬 15 分钟。超时不 resume。
6. 合并只由主会话串行做。合并后立刻 `xr verify`。通过才 `xr done`。冲突大就退回新单元。
7. 派发前若熔断已开，Brief 的 MODEL 写 bai/deepseek-v4.1-flash thinking high。工具尚未调用就失败时，子代理 fallbackModels 会切。已经调用过工具就重新派发到 bai，带上 diff 和 notes，算一次尝试。
8. 失败按 references/failure-modes.md。验证连续失败 2 次就 abandoned 并重做计划。
9. 单元做完后由 x-run-guard 在边界上决定继续、派子代理或压缩。压缩内容以胶囊为准。</procedure>
  <quality_check>doing 单元的文件集互不相交。每个 done 都有 VERIFIED。</quality_check>
  <exit>frontier 空或预算到 70%：读 stages/review.md 或 stages/land.md。</exit>
</stage>
