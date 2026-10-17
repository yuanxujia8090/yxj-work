# x-rail v3 实现报告

分支：`v3-impl`（从 `v3` 的 `317cedd` 拉出）。没有开 PR，没有改其他分支，没有动用户的 `~/.pi`，没有跑 `skills-cleanup.sh`。

## 各阶段做了什么

### P0

本机取证是你在 Mac 上做完的（pi 1.3.0，批次 A 已跑）。仓库里补了三份记录，没有重跑会话挖掘：

- `plans/v3/p0-facts.md`：1.3.0 的事件和 API 都标了「有」。子进程是否加载扩展、`toolBudget`、`~/.agents/skills` 是否共用、yxj-work 在哪、bai 压缩费用，仍是待确认。
- `DECISIONS.md`：C1–C7 和压缩模型。
- `plans/v3/baseline-metrics.json`：数字摘自 01 / 06。这里没有 `sessions.tgz`，没有重跑 `evidence/mine.py`。

### P1

只提交了配置片段，没有改任何本机 settings。文件在 `skills/x-rail/config/examples/`。

- 1.1 bai `supportsDeveloperRole: false`
- 1.2 `maxRetries` 1、`baseDelayMs` 5000、`maxAgentDelayMs` 30000。必须和 x-failover 一起用。
- 1.3 `httpIdleTimeoutMs` 120000，当 A/B。
- 1.4 worker 45 分钟、reviewer 25 分钟、researcher/scout 15 分钟，fallback 为 `bai/deepseek-v4.1-flash`。没有写 `toolBudget`。
- 1.5 压缩模型 `bai/deepseek-v4.1-flash`，thinking `low`，外加 `x-failover` 块。

### P2

`skills/x-rail/extensions/`。

- `mock26.mjs`：本地 OpenAI 兼容服务，按脚本返回 503 账号池、concurrency_limit、busy、超时、524、422 developer。
- `classify.ts`：E0 用户中止，E1 立即切换，E2 同模型再试一次，E3/E5 立即切换，E4 在兜底模型上停止以免循环。
- `breaker.ts`：状态在 `X_FAILOVER_STATE` 或 `~/.pi/agent/state/x-failover.json`。首次冷却 15 分钟，再次翻倍，上限 60 分钟。切回后 15 分钟内再熔断，本 run 留在 bai。
- `switch.ts` / `failback.ts` / `compat.ts` / `subagent.ts`：切换、切回、先压缩再切换、并发 5/2/5，熔断后 2/1/2。
- `x-failover.ts`：挂 `agent_before_settle`，`setModel` + thinking high，写入 custom message 和 `events.jsonl`。`/x-failover status|off|on`。
- 第二兜底 beef-ds 没有启用。探活默认不发网络请求：冷却结束后，在单元边界直接切回。

### P3

`skills/x-rail/scripts/xr`。run 在 `.work-docs/runs/<YYYYMMDD-HHMM-slug>/`。

动词：`init`、`plan add`、`next`、`verify`、`done`、`fail`、`decide`、`gate`、`status`、`capsule`、`import`。

- 没有对应当前 tree hash 的 VERIFIED，`done` 拒绝。
- 依赖有环拒绝。重叠文件不会同时 `doing`。熔断打开时同时只派 1 个写入单元。
- 达到 5 个单元记成子代理模式。
- `capsule` 不超过 2048 字节。
- `import` 不改旧任务文件。
- 参数错误时输出可以复制的正确命令。
- `task.py` 没删，v3 完成不看它。

### P4

`x-run-guard.ts`。

- 有 active run、判据未满足、不是用户中止、也不是 provider 错误时，自动续跑。连续 3 次指纹不变，或剩余单元全被 gate 挡住，就写 `handoff.md` 并停下。
- 有 active run 时，`session_before_compact` 用胶囊当摘要。bai 补充段超过 120 秒或失败就只用胶囊。默认找不到 bai 模型时也只用胶囊，所以这里不会打付费接口。
- `xr done` 写下 `pending-boundary.json`。边界上按 PHASE-BOUNDARIES 选择继续、子代理或 `compact()`。扩展不能新建会话时，`new-session` 改走压缩。
- `session_start` 提示 `/x-rail resume`。
- 流式 180 秒没有 token 就 `abort()`，并记成 E5。

### P5

- `docs/authoring.md`
- `scripts/self_check.py`：入口 ≤ 5120 字节，阶段卡 ≤ 6144，两者之和 ≤ 12288。当前入口 4545 字节。
- `stages/frame.md`、`plan.md`、`execute.md`、`review.md`、`land.md`
- `references/`：外部技能、失败类型、Brief、精简验证、旧证据模式
- `SKILL.md` 指向阶段卡，并去掉了 `disable-model-invocation`。检查器只对 `x-rail` 放开这一条，其他技能仍必须带它。
- 原 playbook 留着。`scripts/test-flow.sh` 和 XML 检查仍要读它们。v3 长任务以阶段卡为准。
- 仓库里没有 `SKILL.md.bak`，所以 `plans/v3/archive/README.md` 只说明这一点。
- `skills/x-rail/install.sh`：`--dry-run`、备份、可重复执行。装 4 个软链和扩展源文件。测试用的是临时 HOME。
- 批次 B 没跑。说明在 `plans/v3/batch-b.md`。

### P6

- `evals/replay/harness.py`：R1–R7 的离线检查（错误分类、胶囊 6 次仍 ≤ 2 KB、cap 不回到 doing、崩溃后磁盘仍是 doing、重叠文件在熔断时只派一个）。
- `--live` 在没有 `XR_REPLAY_APPROVED=1` 时退出码 2，不调用模型。
- `plans/v3/verification-report.md`
- 没有第二模型的独立审查，也没有前后指标的新实测。

## 提交

从旧到新：

| 提交 | 说明 |
|---|---|
| `6c4927e` | P0 事实、决定、基线 |
| `93b42b0` | P1.1 bai compat |
| `93d269f` | P1.2 retry |
| `a4c8710` | P1.3 http idle |
| `75f647f` | P1.4 子代理超时 |
| `1f1e7dc` | P1.5 压缩模型 |
| `908cb55` | mock26 |
| `e2f11af` | 错误分类 |
| `278686c` | 熔断器 |
| `63e67c0` | 切换决策 |
| `b379afd` | 切回 |
| `ce7ef71` | 先压缩再切换 |
| `2c412f8` | 子代理并发 |
| `878895d` | x-failover 扩展 |
| `1214666` | x-run-guard |
| `42f49f3` | xr |
| `d853982` | authoring |
| `a795691` | self_check |
| `38eb38a` | frame / plan |
| `72b16ff` | execute |
| `e259de7` | review / land |
| `0d028f0` | 入口路由 |
| `48f2c09` | 外部技能清单 |
| `6b3c1ca` | install.sh |
| `2216f4d` | 批次 B 不执行 |
| `d85db09` | 回放台与验证记录 |

P3 的几个动词在同一个 `xr` 里，一次提交，测试覆盖了 init、环、frontier、verify/done、fail、幂等 status、胶囊大小、import 哈希和错误提示。

## 跑过的测试

全部通过：

- `python3 scripts/test-xr.py`（5）
- `bash scripts/test-failover.sh`（分类、熔断、切换、切回、mock26）
- `bash scripts/typecheck-extensions.sh`（pi-coding-agent 1.3.0）
- `python3 scripts/test-v3-self-check.py`（3，含超长阶段卡必须失败）
- `bash scripts/test-install-v3.sh`（临时 HOME）
- `python3 evals/replay/harness.py`（R1–R7 离线通过；live 未跑）
- `python3 evals/replay/harness.py --live` 退出码 2
- 原有检查：`check-repo.sh`、`test-flow.sh`、`test-skill-metadata.sh`、`test-skill-xml.py`、`test-contract.sh`、`test-fixtures.sh`、`test-install.sh`、`test-v2-lifecycle.sh`、`test-worktree.sh`、`test-coordination.py`（11）、`test-frontier.py`（5）、`test-html-check.py`、`test-repo-boundary.py`、`test-self-check.py`（15）、`test-task-checklist.py`（7）、`test-task-checks.py`（72）、`test-work-items.py`（17）、`test-document-template.sh`

## 没做的事

- 没有把配置片段写进你的 `models.json` / `settings.json`。
- 没有对真实 HOME 运行 `install.sh`。
- 没有跑批次 B，也没有跑批次 A（你已经在 Mac 上跑过 A）。
- 没有用真实模型跑 R1–R7。原始仓库不在这个环境里。
- 没有启用 beef-ds 第二兜底。
- 没有发探活请求。
- 没有删旧 playbook，也没有删 `task.py`。
- 没有独立审查，没有新的线上指标。

## 在 Mac 上安装

1. 拉下分支 `v3-impl`。
2. 先看会改什么，不要直接装到真 HOME：

```bash
bash skills/x-rail/install.sh --dry-run --home "$HOME"
```

3. 确认输出只有 4 个软链（`x-rail`、`x-handoff`、`x-worktree`、`x-self-check`）和扩展文件。然后：

```bash
bash skills/x-rail/install.sh --home "$HOME"
```

已有同名文件会先备份到 `~/.pi/agent/v3-backup-<时间>/`。再跑一次应该显示「已是目标软链」。

4. 对照 `skills/x-rail/config/examples/`，自己把片段并进 `~/.pi/agent/models.json` 和 `settings.json`。不要把 apiKey 写进仓库。1.2 和 x-failover 一起启用。

5. 新开一个 pi 会话，确认技能列表里有 `x-rail`（它不带 disable-model-invocation）。`/skill:x-handoff`、`/skill:x-worktree`、`/skill:x-self-check` 仍是手动。`/x-failover status` 能看熔断。

6. 在一个临时仓库里跑：

```bash
skills/x-rail/scripts/xr init demo
skills/x-rail/scripts/xr status
python3 skills/x-rail/scripts/self_check.py --root <仓库> --skills-dir "$HOME/.agents/skills"
```

7. self_check 通过、新会话能看到 x-rail 之后，再看批次 B：

```bash
bash plans/v3/evidence/skills-cleanup.sh --batch B --dry-run
```

确认守卫通过后再去掉 `--dry-run`。这一步会归档 11 个全局技能，只归档，不删除。

8. 付费回放另说。批准之后：

```bash
XR_REPLAY_APPROVED=1 python3 evals/replay/harness.py --live
```

当前 `--live` 仍只是门闩，不会自己去打模型。真正用 openai26 / bai 重放 R1、R2 还要你提供原来的仓库，或接受用结构相近的测试仓库代替。

## 还没定的问题

- pi-subagents 0.76.1 的 `agentOverrides` 键名，以及单个代理能不能设 `toolBudget`。
- 子 pi 进程会不会加载 `~/.pi/agent/extensions`。不会的话，中途失败只能靠主会话重新派发（阶段卡已经这样写）。
- `~/.agents/skills` 是否还被别的工具共用。批次 B 会同时影响那些工具。
- yxj-work* 现在在哪个目录。
- bai 做压缩的费用。扩展在 120 秒后放弃补充段，但 smartCompact 本身仍可能打一次 bai。
- 要不要启用 beef-ds 作为第二兜底。
- 回放用的网站仓库和编码仓库能不能拿到。拿不到就用替身仓库，并在结果里写明。
