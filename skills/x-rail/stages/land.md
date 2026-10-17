# Land

<stage name="land">
  <inputs>最终树、RUN.md 的 Done 判据、ledger。</inputs>
  <procedure>1. 在最终树上跑全量测试或 typecheck。没有这次证据就不能说完成。
2. 对照 Done 判据逐条写是否成立，并指向命令输出。
3. 交付 brief：做了什么、哪条判据、哪个模型做的、没验证什么、下一步。人工检查放在这份 brief 里，不在执行中途打断。
4. 墙钟到 100%，或无进展，或剩下的单元全被 gate 挡住：写 handoff.md（已完成、未完成、阻塞、下一条命令都只给路径），可调用 x-handoff。
5. Reflect：调用 x-self-check。改进优先做成自动检查。用户纠正追加到 Standing orders。失败样本记到回放说明，不另开一套流程。</procedure>
  <quality_check>brief 里的每条完成声明都能在 ledger 或最终测试输出里找到。</quality_check>
  <exit>run 可以停下。新会话从 capsule.md 和 `xr status` 恢复。</exit>
</stage>
