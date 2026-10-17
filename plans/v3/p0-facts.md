# P0 事实记录

P0 的本机取证由用户在 Mac 上完成。本文件只记录已经核实的事实，以及本仓库实现所依赖的结论。本环境没有用户的 `~/.pi`，也没有 sessions 语料，不能代替 Mac 上的复查。

时间：2026-10-17。pi 版本以用户实测为准。

## 0.1 pi 版本与扩展 API

用户已把 pi 升到 **1.3.0**（npm 包 `@earendil-works/pi-coding-agent`）。本环境安装了同一版本，对照 `dist/core/extensions/types.d.ts`，下列 API 都**有**：

| API | 结论 |
|---|---|
| `agent_before_settle` | 有。结果类型 `BoundaryResult`：`entries?`、`continue?` |
| `agent_settled` | 有。字段 `aborted` |
| `session_before_compact` | 有。`preparation`、`branchEntries`、`customInstructions`、`reason: manual\|threshold\|overflow`、`willRetry` |
| `session_compact` / `session_compact_failed` | 有 |
| `before_provider_request` / `after_provider_response` / `provider_stream_event` | 有 |
| `model_select` / `turn_end` / `message_end` | 有 |
| `tool_call` | 有，处理函数可以拦住调用 |
| `tool_result` | 有 |
| `ui_prompt_start` / `ui_prompt_end` | 有 |
| `session_start` / `session_shutdown` | 有 |
| `message_update` | 有（看门狗用它判断还有没有 token） |
| `setModel(model): Promise<boolean>` | 有。`false` 表示该 provider 没有认证 |
| `setThinkingLevel` | 有 |
| `sendUserMessage(content, opts)` | 有 |
| `compact(opts)` | 有。不等待完成 |
| `getContextUsage()` | 有。返回 `{ tokens, contextWindow, percent }`，tokens 可能是 null |
| `abort()` | 有 |
| `modelRegistry.find(provider, id)` | 有 |
| `modelRegistry.complete(...)` | 有。压缩补充段用它，失败就退回胶囊 |

`session_before_compact` 的返回值可以带 `compaction`（`summary`、`firstKeptEntryId`、`tokensBefore`），用来替换默认摘要。扩展因此可以在压缩结果里放胶囊。

## 0.2 pi-subagents、smart-compact、子进程

本环境没有安装 pi-subagents 0.76.1，也没有 pi-smart-compact 的源码，下面几项仍是**待确认**（不影响本仓库按 04 的推荐路径写代码）：

- `agentOverrides`、`fallbackModels`、`timeoutMs` 的真实 schema 以 0.76.1 为准。仓库里的配置片段按 04 §6 的键名写，用户批准后再贴进本机 settings。
- 单个代理能否设置 `toolBudget`：未知。阶段卡把「不超过 40 轮」写进 Brief；`toolBudget` 约 60 先不写进会报错的配置。
- 子 pi 进程是否加载全局扩展：未知。代码两条路都留了：子进程里有 x-failover 就在内部切换；没有就由主会话按 03 §10.5 重新派发。
- resume 时能否覆盖模型：未知。超时后的路径是重新派发，不 resume。
- pi-smart-compact 与 x-run-guard 都挂 `session_before_compact` 时谁先执行：未知。x-run-guard 在有 active run 时直接返回 `compaction`，摘要以胶囊为准，bai 补充段失败也不阻塞。这样不依赖执行顺序。

## 0.3 仓库状态

实现开始时分支是 `v3`，工作区干净，HEAD `317cedd`。v3-goal 里「最终提交未完成」的那批改动已经在 `v3` 上。本次实现在新分支 `v3-impl`，不改其他分支。

## 0.4 `task.py` 依赖

`task.py` 仍是证据模式和 CI 的检查器。v3 长任务不调用它来判定完成。调用点归属：

| 位置 | 归属 |
|---|---|
| `skills/x-rail/scripts/task.py` 及 `task_checks.py`、`check-*.sh` | 保留。旧任务和现有测试继续用 |
| `scripts/test-*.sh`、`scripts/test-*.py` | 保留。只读兼容 |
| 阶段卡 `stages/*.md` | 不把 `task.py` 当主路径。完成看 ledger |
| `references/legacy-evidence-mode.md` | 只读说明：旧证据模式仍用 task.py |

不删除 `task.py`，也不改它的子命令。

## 0.5 / 0.5b 技能与加载

- 批次 A 已由用户在 Mac 上执行。本环境不运行 `skills-cleanup.sh`。
- `~/.agents/skills` 会被加载这一点，07 已从会话 `<location>` 确认。是不是还被 Codex 或其他工具共用：本环境无法看用户机器，仍**待确认**。脚本只归档、可恢复。
- yxj-work* 现在在哪：inventory 里没有，本环境没有 `~/.pi`，仍**待确认**。实现不依赖它们。
- package 自带技能能否单独屏蔽：未知。v3 不改 package 技能。

## 0.6 决定

见仓库根目录 `DECISIONS.md` 2026-10-17 一节，以及 `plans/v3/05-目标与挑战对照表.md` §8。

## 0.7 基线指标

`baseline-metrics.json` 的数字摘自 01 / 06 的对照表。本环境没有 `sessions.tgz`，没有重跑 `evidence/mine.py`。
