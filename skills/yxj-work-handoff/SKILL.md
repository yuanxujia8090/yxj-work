---
name: yxj-work-handoff
description: 将当前 yxj-work 任务写入 .work-docs/tasks/<task-id>/handoff.md，供新会话继续。
disable-model-invocation: true
---

# yxj-work-handoff

本技能只能由用户主动调用。`yxj-work` 或 `yxj-work-long` 不得因为任务进入交接阶段而自动触发本技能。

交接文件只能写入当前任务的 `.work-docs/tasks/<task-id>/handoff.md`，不得写入工作区外部的交接目录。`<task-id>` 是完整目录名，形如 `20260928-01-yxj-work-independent-workflow`。

执行顺序：

1. 读取 `state.md`、`contract.md`、最近 checkpoint 和 evidence。
2. 读取每条 evidence 的 `command`、`run_at`、`result` 和相关文件 `last_edit_at`；只有 `run_at` 不早于相关文件最后修改时间时才重跑契约验证，否则直接引用新鲜证据。每次重跑都记录真实结果。
3. 更新 `handoff.md`，包含背景、done_when、当前阶段和 status、验证输出、已完成、下一步第一动作、卡点与已尝试策略、约束、待拍板、关键文件和 evidence 路径。
4. 如果任务熔断，记录 `blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition` 和禁止重复的策略指纹。
5. 自检：新会话只读 handoff 后能直接执行 next_action 第一条。
6. 在 handoff 末尾写“下一会话第一步”，内容必须与 `next_action` 第一条一致，并列出最近 checkpoint 和 evidence 路径。

## 下一会话第一步

新会话先读本文件，再读 `state.md`、最近 checkpoint 和 evidence；输出当前状态、已完成、下一步第一动作、阻塞和证据位置，然后才执行任务。handoff 是状态入口，不是完成证明；没有 required evidence 时不得写 `status: done`。
