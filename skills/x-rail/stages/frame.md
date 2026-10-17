# Frame

<stage name="frame">
  <inputs>用户目标、仓库现状、已有 run。只读代码和文档，先不改业务文件。</inputs>
  <procedure>1. 调用 Skill 工具 grilling。每题附推荐答案，用户回 yes 即接受。只问单向门：公共接口、数据模型、删除、花钱、发布、范围。能自己查到的事实不问。
2. `xr init slug`。把一句话目标写入 RUN.md 的 Intent，把可数判据写入 Done。
3. 看 Autonomy 里的 preflight。缺命令或技能时记下来，能绕开就绕开。
4. Standing orders 保留「本地 wip 可以提交、不推送」。用户本轮拒绝时，`xr decide "改用 patch" --why "用户拒绝 wip"`。
5. Budgets 写墙钟。用户说成本不限时，只保留墙钟，并 `xr decide` 记下原话。
6. 领域词不清楚时调用 Skill 工具 domain-modeling，结论写 decisions，不另起文档。
7. `xr status`。Done 判据、单向门和 Budgets 都有了才离开本阶段。</procedure>
  <quality_check>RUN.md 能让另一个会话说清「怎样算做完」。preflight 段不是空的。</quality_check>
  <exit>下一张卡是 stages/plan.md。执行期不再提问；新问题用 `xr gate "问题" --default "默认"`。</exit>
</stage>
