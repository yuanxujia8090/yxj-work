# Brief

子代理只按这张表派发，不手写 workflow 语法。

```
GOAL       一句话
SCOPE      --files；worktree 与分支 xr/run/unit；基于集成分支 SHA
CONTEXT    只给指针：RUN.md#Intent、units.tsv 那一行、notes/、起点 SHA
ACCEPTANCE 可检查的条件
VERIFY     一条命令
BUDGET     ≤ 40 轮；软 30 分钟写进度；硬超时 45 分钟
MODEL      主模型；熔断时 bai/deepseek-v4.1-flash thinking high
FORBIDDEN  文件集之外不改；不推送；不 rebase 集成分支
REPORT     notes/单元-report.md、wip 提交、一行摘要
STANDING   RUN.md#Standing。答不上的问题写 xr gate，不停下空等
```
