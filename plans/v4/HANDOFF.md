# v4 交接（HANDOFF）

> 交接时间：2026-10-20 19:36（Asia/Shanghai）
> 交接人：上一会话（父会话）
> 下一会话入口：**直接在 `/Users/yuanxj/Documents/github/x-rail/.worktrees/v4` 打开**
> 状态：**只写了方案文档，没有任何代码改动**

## 0. 先做三件事

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
git status --short --branch
git rev-parse HEAD
```

期望：

```text
## v4
?? plans/v4/
d44133bc2efcefe8960a84a1faea59c9d4296605
```

然后读 `plans/v4/00-README.md`（结论）与 `plans/v4/03-实施计划.md`（怎么干）。不要先读别的历史计划，容易混淆版本。

## 1. 当前事实

| 项 | 值 |
| --- | --- |
| 工作树 | `/Users/yuanxj/Documents/github/x-rail/.worktrees/v4` |
| 分支 | `v4`（从 `v3` 的 `d44133b` 起） |
| HEAD | `d44133bc2efcefe8960a84a1faea59c9d4296605` |
| 已跟踪文件改动 | 无 |
| 未跟踪 | `plans/v4/`（5 个文件，1114 行） |
| 提交 | **未提交** |
| 推送 / 安装 / 改 `~/.pi` | **均未做** |
| 主仓库 | `/Users/yuanxj/Documents/github/x-rail`，`main`，工作区干净 |
| v3 工作区 | `/Users/yuanxj/Documents/github/x-rail/.worktrees/v3`，仅有 `?? plans/0.0.10/`，**未动** |

`.worktrees/` 已被 `.gitignore:7` 忽略，主仓库 `git status` 不会看到 v4 的内容。

## 2. 已经完成什么

- 创建并迁移了 v4 工作树（先建在仓库外，后按用户要求移到 `.worktrees/v4`）。
- 写了 `plans/v4/` 五份文档：

| 文件 | 行数 | 内容 |
| --- | --- | --- |
| `00-README.md` | 73 | 结论、与 v3/0.0.10 的增量、原则、非目标 |
| `01-证据与缺口.md` | 95 | 18 条源码事实（带行号）、Pi 1.3.0 能力表、8 个缺口、未验证项 |
| `02-技术方案.md` | 349 | 四层架构、状态契约、`xr` 接口、恢复优先级、错误映射 |
| `03-实施计划.md` | 528 | 7 个 TDD 任务、16 条验收矩阵、命令总表、回滚 |
| `DECISIONS.md` | 69 | 17 条决策、明确不做项、行为变化、待拍板项 |

取证依据（本轮真实读过）：

- 源码：`skills/x-rail/extensions/{run-files,x-run-guard,x-failover,classify,switch,guard-core,store}.ts`、`skills/x-rail/scripts/xr`、`evals/replay/harness.py`。
- 宿主类型：本机 `@earendil-works/pi-coding-agent` **1.3.0** 的 `dist/core/extensions/types.d.ts`（非猜测）。
- 历史运行：`plans/0.0.10/近三日运行分析.md` 中的 `01a149b6`、`01a15332`。

上次验证（真实执行）：

```text
bash scripts/check-repo.sh
Ran 13 tests in 5.556s
OK
check-repo: passed
```

这只证明**现有仓库回归未被我改动破坏**，不证明 v4 方案已实现。

## 3. 方案一句话

**模型提议，宿主记录，检查器裁决。**

四层：

```text
L0 宿主适配层（Pi 扩展）：记录事实、执行已批准的恢复动作
L1 任务层（x-rail 技能）：决定下一步做什么
L2 权威检查器（xr CLI）：唯一有权说“完成/未完成”
L3 运行数据（磁盘）：唯一真相
```

只做四件事：

1. **运行身份**：`binding.json` = `workspace + run_id + session_id`；`ACTIVE` 只作发现入口。
2. **工具生命周期**：`op_intent` / `op_result` 配对；未配对的写操作一律暂停，不重放。
3. **统一恢复**：`decideRecovery()` 单一入口；看门狗只报告，不自行换模型。
4. **完成门**：`xr inspect` + `acceptance.tsv` + `finish.json`；`done` 也复核证据。

## 4. 必须保留的既有决策

- **E2（瞬时错误）仍是“同模型再试 1 次”**，之后才切换或交接。不要改成直接切模型。
- 余额 / 鉴权 / 额度错误：**停止**，不重试不切换。
- 未知错误：**暂停**，保存原文。
- 主模型 `openai26/gpt-6.1-sol`，兜底 `bai/deepseek-v4.1-flash`（thinking high）；**不新增第三模型**。
- 每 run 最多 failover 8 次、无进展 failover 2 次、续跑 200 次、无进展续跑 3 次；**不提高上限**。
- 不做预算 70% 自动收尾、不做付费回放、不做个人 HOME 安装。

## 5. 下一步怎么做

按 `plans/v4/03-实施计划.md`：

| 顺序 | 任务 | 依赖 | 备注 |
| --- | --- | --- | --- |
| 1 | `xr inspect` + `acceptance set/list` | — | 与任务 3 可并行（文件不相交） |
| 2 | `finish` / `pause` / `resume` + `done` 复核 | 任务 1 | 改 `close` 语义前需用户拍板 |
| 3 | 运行绑定 + `inspect` 客户端 | 任务 1 的接口 | 删除 `runSnapshot` |
| 4 | 工具意图 / 结果记录 | 任务 3 | 新建 `host-events.ts` |
| 5 | 统一恢复入口 | 任务 3、4 | 新建 `recovery.ts` |
| 6 | 真实宿主生命周期测试 | 任务 3–5 | 本地假模型，不连真实 provider |
| 7 | 文档与回放标注 | 1–6 | `check-repo.sh` 收尾 |

每个任务一条提交；**先写失败测试，再实现**。任务 1 的第一条测试代码已写在计划里，可直接复制。

## 6. 五个待拍板项（在 `DECISIONS.md` §5）

| # | 问题 | 默认 |
| --- | --- | --- |
| Q1 | 是否新增 `binding.json` / `acceptance.tsv` / `finish.json` | 按方案新增 |
| Q2 | `close` 是否必须有 `finish.json`，否则标为“未证明完成” | **先只改原子性，不改语义** |
| Q3 | 旧运行是否批量接入新标准 | 不批量，逐个显式 |
| Q4 | `inspect` 超时 5 秒是否可接受 | 保持 5000，可配置 |
| Q5 | 是否先只启用完成门、暂不启用自动恢复 | 允许，分两步 |

Q2 会改变现有行为，实施到任务 2 前需要用户明确同意；其余按默认执行即可。

## 7. 容易踩的坑

1. **不要用 `git worktree add` 再建一个 v4。** 已存在，`git worktree list` 可见。
2. **不要删除或重置 `plans/0.0.10/`。** 它在 v3 工作区，是未跟踪但有用的取证材料。
3. **不要把 v4 文档当成已实施。** 文档里所有“将新增/拟新增”都还没写代码。
4. **不要凭 `runSnapshot` 判断完成。** 计划要求删除它，改用 `xr inspect`。
5. **不要假定子代理会进入父会话事件流。** 这是未验证项，实施任务 6 时才测。
6. **`xr` 现有 `done` 幂等语义会变**：从“已 done 直接 unchanged”改成“复核证据”。改测试断言是预期行为。
7. **`plans/v4/` 未提交。** 如果切目录后想长期保留，先提交一个文档提交，例如：

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
git add plans/v4
git commit -m "docs(x-rail): add v4 design plan"
```

（提交前确认没有把 `.work-docs/` 运行数据带进来；`git status` 应只有 `plans/v4/`。）

## 8. 复现与验证命令

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v4
python3 scripts/test-xr.py -v
bash scripts/test-failover.sh
bash scripts/typecheck-extensions.sh
python3 evals/replay/harness.py --out /tmp/xr-replay.json
bash scripts/check-repo.sh
```

说明：

- `typecheck-extensions.sh` 首次运行会 `npm install`（在 `skills/x-rail/extensions/`），需要网络；若不想安装，跳过并注明“未验证”。
- `evals/replay/harness.py --live` 当前名不副实，计划任务 7 才修。
- 任何声称“完成/通过”，必须贴出实际命令与输出。

## 9. 交接范围

本次交接**只包含设计与文档**，不包含：

- 任何代码改动；
- 任何个人 Pi 配置或扩展安装；
- 任何推送、发布、生产操作；
- 任何真实模型付费调用。

在新会话里继续时，先确认上面第 0 节的三条命令输出与本文一致；不一致就先查清差异，再动手。
