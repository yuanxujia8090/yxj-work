# Review

<stage name="review">
  <inputs>集成分支相对 run 起点的 diff，ledger。</inputs>
  <procedure>1. 低风险单元只看 ledger 里的命令证据。
2. 高风险（公共接口、数据、安全）和 Land 之前：调用 Skill 工具 code-review，两轴（Standards 与 Spec）。
3. 可共读固定输入，报告独占；记录审查者、输入版本和报告。无报告不算完成。
4. 故障先查原运行：活跃则续接，终止后接收报告并补审，未知则暂停；不另设宿主外期限。
5. 评审发现的问题用 `xr plan add` 写成新单元，回到 Execute。没有新问题时离开。</procedure>
  <quality_check>高风险单元有另一家族的评审记录，或写明同家族补审。</quality_check>
  <exit>读 stages/land.md。</exit>
</stage>
