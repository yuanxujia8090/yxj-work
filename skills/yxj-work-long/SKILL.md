---
name: yxj-work-long
description: 跨阶段、跨会话、过夜或长时间外部运行的 yxj-work 入口；使用 .work-docs checkpoint 和熔断。
disable-model-invocation: true
---

# yxj-work-long

命令后的文字是长任务说明。本 skill 独立运行，不读取旧工作流 skill。

## 进入判据

单一配置核查、单文档整理、一个小 bug 或小型只读分析走普通 `yxj-work`。满足跨两个以上阶段、跨会话/过夜、多个子任务、长时间外部运行、研究→决策→开发交接或证据明显超出普通阈值之一时进入长任务。

## 开工

在当前命令执行目录初始化唯一 `.work-docs`，创建 L3 任务契约和状态。每个阶段写文件范围、done_when、验证命令、依赖和产物位置。父任务及子任务都必须使用唯一 task id。

## 进展、预算和熔断

有效进展只有两种：某个 `done_when` 条目拿到新 evidence，或某个 required 验证从 `failed|not_run` 变为 `passed`。每次有效进展都更新 `state.md` 的 `calls_since_progress`（归零）、`last_progress_at`、`budget`（`used/limit`）和 `strategy_fingerprints`。`evidence freshness`（证据新鲜度）按 `run_at` 不早于相关文件 `last_edit_at` 判断；交付时关键词或 grep 检查只标为 `static`。

每个子任务独立计算：60 次工具调用或 30 分钟无进展、同一命令与同一错误首行出现 2 次、错误不同但 required 验证连续失败 3 次、越界写入或共同前提被否定，立即熔断。同一类工具或命令报错 2 次必须换方法，不能原样重试；错误各不相同时，required 验证连续 3 次失败也必须熔断。默认总预算为 400 次工具调用或 8 小时；任务说明显式指定预算时，以任务说明为准。总预算耗尽写最终 checkpoint，不标记 done。

策略指纹固定为 `修改文件 + 执行命令 + 错误首行`，记录在 `audit/`。恢复时，新指纹不能与已有指纹相同；说不出新旧策略差异就停下交给用户。

熔断后：

1. 停止当前子任务修改和同策略重试；
2. 在 `audit/` 写失败动作、错误摘要、策略指纹、证据指针；
3. 将 `state.md` 设为 `blocked`，填 `blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；
4. 写 checkpoint 或 handoff；
5. 父任务不得 `done`；只有不依赖阻塞项的独立子任务可继续。

恢复只能来自阻塞解除、共同前提重新验证通过或有 evidence 的新策略。恢复前先读 state、checkpoint、失败策略和 evidence，不重复相同策略。required 子任务 active、blocked、stopped 或 required 验证为 failed/blocked/not_run 时，父任务不得 done；optional 子任务必须在契约中显式声明。

## Checkpoint

每个阶段结束追加 checkpoint：状态、done_when、真实验证输出、证据指针、下一阶段依赖、阻塞、解除条件和下一步第一动作。跨会话入口读取 state、handoff、目标/进度文件和最近产物，不依赖会话记忆。

## 交付

只有 required 验证全部 passed、决策门允许、无越界文件、required 子任务结束且所有结论有 evidence 才能 done。否则交付 `blocked`、`stopped`、`design_only`、`gather_more` 或 `do_not_build` 的真实状态。
