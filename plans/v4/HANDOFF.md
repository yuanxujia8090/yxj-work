# v4 交接（HANDOFF）

> 交接时间：2026-10-21（Asia/Shanghai）
> 状态：**部分实现，任务暂停**。`xr` 检查器与运行绑定已落地；工具配对、统一恢复、生命周期测试未做。

## 0. 先确认现场

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
git status --short
git log --oneline -3
bash scripts/check-repo.sh
```

期望：工作区干净，`check-repo: passed`。

## 1. 已经落地的实现

### 1.1 `skills/x-rail/scripts/xr`

新增动词与语义：

- `inspect --json`：唯一完成判断。规则见 `02-技术方案.md` §3.3；`mode` 分 `managed / legacy / invalid`，`legacy` 只读。
- `acceptance set|list|rebind`：需求语句绑来源（文件摘要或会话条目）与单元；`rebind` 一次替换 `units` 列。
- `finish`：通过 `inspect` 才写 `finish.json`（含 `dispatch_epoch`、四份摘要），失败保留现场。
- `pause` / `resume --confirm [--take-ownership]`：`pause` 不递增 epoch、不丢 `ACTIVE`；`resume` 改 phase 与 lease、把旧 `finish.json` 改名 `finish.invalid.json`、记录 `took_over_from`。
- `bind --session <id>`：唯一写入 `binding.json`；别的会话 `lease=active` 时拒绝。
- `done`：删掉“已 done 直接 unchanged”，改为每次复核当前文件与命令摘要。
- `close`：不强制 `finish.json`（Q2 仍按默认），但把收据状态写进 `closed` 与事件。
- `--run-id`：显式无效直接退出 2，不回退 `ACTIVE`；目录必须落在 `runs/` 下。
- `RUN.md` 新字段：`format_version`、`dispatch_epoch`、`phase`、`review_required`。

`ensure_consistent()` / `automation_blocked()`：结构损坏或 phase/lease 非执行态时，`next` / `done` 拒绝推进。

### 1.2 扩展

- `run-files.ts`：新增 `parseBinding` / `bindingMatches` / `readBinding` / `inspectRun`（异步 `execFile`，5 秒超时，失败返回 null）；**删除 `runSnapshot`**。
- `x-run-guard.ts`：绑定改为会话级固定 `{runId, sessionId, dir}`；`session_start` 调 `xr bind` 一次；`guardBoundary` 用 `xr inspect`，指针漂移只提示不接管，检查器无结果按暂停处理并写 `handoff.md`。
- `asksUser` 去掉“结尾问号”单独触发（D16）。

### 1.3 探针与测试

- `plans/v4/evidence/host-probe.md`：真实 Pi 1.3.0 + 本地假模型，13/13 断言两组；结论是阻断调用**没有** `tool_result`、子代理启动回执**不等于**终态、父子归属只能用各自 `sessionId`。
- `scripts/test-run-lifecycle.mjs` + `scripts/fixtures/run-lifecycle/`：上述探针的可重跑入口（`node scripts/test-run-lifecycle.mjs`）。
- `scripts/test-xr.py`：13 → **22 tests**，覆盖 A1–A7、A15、A17–A19。

## 2. 本机验证结果（真实执行）

```text
python3 scripts/test-xr.py -v      → Ran 22 tests ... OK
bash scripts/typecheck-extensions.sh → typecheck-extensions: passed
node --experimental-strip-types skills/x-rail/extensions/failover.test.ts → failover tests passed
bash scripts/check-repo.sh         → OK / check-repo: passed
node scripts/test-run-lifecycle.mjs → 13/13（见 evidence/host-probe.md）
```

## 3. 还没做（按依赖顺序）

| # | 任务 | 关键点 |
| --- | --- | --- |
| 1 | `host-events.ts` | `tool_call` → `op_intent`（含 `side_effect`），`tool_result` → `op_result`；**被阻断的调用没有 `op_result`**，收尾只能靠 `turn_end` / `agent_settled` 补记，不能等 `tool_result` |
| 2 | `x-failover.ts` 改用固定绑定 | 现在仍按 `findActiveRun` 计 `toolCallsSinceFailover`，子代理与漂移都会污染计数 |
| 3 | `recovery.ts` + `classify` 补 502/断流 | 统一入口、共用上限；看门狗只报告 |
| 4 | 子代理启动 vs 终态 | 启动回执只算 `started`；终态必须查 status/事件/通知，`parentToolCallId` 不能当父子键 |
| 5 | 生命周期测试扩场景 | 现有探针覆盖加载/阻断/异步；还缺 reload 后读绑定、检查超时、recovery 上限 |
| 6 | 阶段卡与 `docs/architecture.md` | 同步 `inspect` / `acceptance` / `finish` / `pause`、`binding.json`、`op_*` 事件 |
| 7 | 独立审查 | 实现者自审不算；至少复核“误判完成”和“越权重放”两类 |

## 4. 下一步第一件事

先做任务 1 的失败测试，再实现 `host-events.ts`：

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
node --experimental-strip-types skills/x-rail/extensions/failover.test.ts   # 先看现状
```

断言目标（写进 `failover.test.ts`）：

- `classifyToolSideEffect("read"|"grep"|"find"|"ls") === "read"`
- `classifyToolSideEffect("write"|"edit"|"bash"|"powershell") === "write"`
- `classifyToolSideEffect("mcp__db__migrate") === "unknown"`
- `unresolvedOps([intent a, result a, intent b]) === ["b"]`

## 5. 不能踩的坑

1. **`plans/0.0.10/` 在 v3 工作区**（未跟踪取证材料），不属于 v4，不要 `git add`，也不要删。
2. **不要让扩展自己判断完成**。只能读 `xr inspect` 的 `done_met`。
3. **被 block 的工具没有 `tool_result`**（已实测）。按 `tool_result` 收尾会让未配对集合永久残留。
4. **子代理启动 ≠ 完成**；`subagent` 的 `tool_result` 只是启动回执。
5. **E2 仍是同模型再试 1 次**；余额/鉴权停止；未知错误暂停。
6. **`close` 目前不要求 `finish.json`**（Q2 未拍板）；要改语义先问用户。
7. **不要推送、不要装到 `~/.pi`、不要调真实模型**。

## 6. 待拍板

见 `DECISIONS.md` §5 的 Q1–Q5。除 Q2 外均可按默认执行；Q2 改 `close` 语义，动之前需要用户同意。

## 7. 验证命令总表

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
python3 scripts/test-xr.py -v
bash scripts/typecheck-extensions.sh
node --experimental-strip-types skills/x-rail/extensions/failover.test.ts
node scripts/test-run-lifecycle.mjs
bash scripts/check-repo.sh
```

任何“完成/通过”的声称都要贴实际输出；本文件第 2 节是上一次真实输出，不是承诺。
