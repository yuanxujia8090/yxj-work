# 工作流任务索引

task-id 即 `tasks/` 下的目录名，格式 `{YYYYMMDD}-{NN}-{slug}`：`{YYYYMMDD}` 为创建当天本地日期，`{NN}` 为当日两位自增序号（从 `01` 起、不回收空号），`{slug}` 为任务短名。取号前先读本文件：有同范围进行中任务则续用原 id，否则取当日最大序号 +1 并追加索引行。

| task-id | scope | status | updated_at |
|---|---|---|---|
| 20260928-01-yxj-work-independent-workflow | 完成 yxj-work 独立工作流仓库并与旧 yxj-mode 隔离 | done | 2026-09-28 |
| 20260928-02-yxj-work-skill-flow-review | 审查 yxj-work 与辅助 skill 的整合，并按结论接入（随安装分发、不可语义唤起、由流程主动读取） | done | 2026-09-28 |
| 20260928-03-yxj-work-flow-evaluation | 优化普通与长任务流程，并验证开发、排查修复、调研和跨天恢复 | done | 2026-09-28 |
