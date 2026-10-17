# Review

<stage name="review">
  <inputs>集成分支相对 run 起点的 diff，ledger。</inputs>
  <procedure>1. 低风险单元只看 ledger 里的命令证据。
2. 高风险（公共接口、数据、安全）和 Land 之前：调用 Skill 工具 code-review，两轴（Standards 与 Spec）。
3. 实现在 openai26 上时，reviewer 用 bai。实现在 bai 上时，reviewer 优先用 openai26。openai26 也在熔断时用 bai，并在 ledger 记「同家族审查」，切回后补审高风险单元。
4. reviewer 硬超时 25 分钟。fixed point 是 run 起点的 SHA。
5. 评审发现的问题用 `xr plan add` 写成新单元，回到 Execute。没有新问题时离开。</procedure>
  <quality_check>高风险单元有另一家族的评审记录，或写明同家族补审。</quality_check>
  <exit>读 stages/land.md。</exit>
</stage>
