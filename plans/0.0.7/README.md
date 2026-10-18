# x-rail 0.0.7：v3 审查问题的核心收敛方案

> 状态：**方案已进入实施收口**。实现已修改被审文件；未执行安装、推送、部署或删除历史证据。本文保留原始方案与取舍，实施状态见 §11。
> 日期：2026-10-17（Asia/Shanghai）。
> 输入：`plans/v3/issue/issue-2026-10-17-session-01a1499c.md`、`plans/v3/review/review-2026-10-17-v3-branch.md`、`plans/v3/review/gork-20261017-x-rail-v3-代码审查报告.md`。
> 方法：先按第一性原理找"哪条不变量被破坏"，再用奥克姆剃刀选出"删掉什么就能修好"，最后用 PStack 原则核对方向。逐条甄别见[issue-matrix.md](issue-matrix.md)。
> 证据纪律：标注「我复核」的是本次实际跑过或读过源码；标注「报告复现」的是引用报告结论、本次未复跑。两者不混写。

## 1. 结论摘要

三份报告合计提出 80 余条编号问题。逐条复核后，**真问题集中在 4 个根因上**，其余是它们的重复症状、已被当前提交修掉的历史项、或需要删掉而不是实现的死代码。

| 核心问题 | 一句话 | 被破坏的不变量 |
|---|---|---|
| **A 宿主控制层有两个互不通气的司机** | 两个扩展在同一宿主生命周期上各自决策，宿主语义是「后者覆盖前者」 | I1 状态在磁盘、会话可被替换 |
| **B 磁盘账本「读整本改整本」** | 并发或中断会丢更新、毁账本 | I3 状态只有一个真相源 |
| **C 完成门认「文件指纹」不认「判据」** | 改了验证命令仍算通过；终态可被改写；修订无合法入口 | I2 完成必须有当前有效证据 |
| **D 两套流程并行且自动续跑越权** | 入口没说何时用哪套；只要存在 active run 就对所有回合强制续跑 | I4 规则少、硬、可检查 |

**不建议按报告的 80 条平铺修复。** 报告里的大多数「必修项」是 A/B/C/D 的下游表现：修掉 A，扩展层的 6 条消失；修掉 B，并发相关的 5 条消失；修掉 C，完成门相关的 7 条消失。

**最重要的判断**：报告的收敛结论「不建议合并」成立，但理由需要更正——**不是 14 个独立缺陷，而是 4 处结构性缺口**。按结构修，改动量约为逐条修的 1/3，且不留同类新坑。

**已修、不要重开的**：`gork` 报告 M1「正常回答被判定为 provider 故障」在 `d6fc6a1` 已修（`classify.ts` 只在 `stopReason === "error"` 时读正文，`failover.test.ts` 有回归断言）。我复核确认。

## 2. 输入与提交边界

三份报告的审查对象**不是同一个提交**，混用结论会出错。

| 报告 | 审查对象 | 视角 |
|---|---|---|
| `issue-...-01a1499c.md` | 一次真实业务修复会话（website 项目 `20261017-01`），不是源码审查 | 用一次真实运行反推 x-rail 的记录/完成门/修订入口缺陷 |
| `review-2026-10-17-v3-branch.md` | worktree `v3`，HEAD `3c8488a`，基线 `b158f20` | 源码审查 + 部分端到端复现（3 个只读子代理） |
| `gork-...-代码审查报告.md` | 提交 `d6fc6a1`，32 个提交 80 个文件 | 独立重审 + 真 pi 1.3.0 + mock provider 端到端复现 |

当前 worktree HEAD 为 `d6fc6a1`。因此：

- `review` 报告标为 M1 的「正常回答误判」在 `d6fc6a1` 已修；`gork` 报告在「做得好的地方」也确认了这次修复。**两份报告对同一项给出不同结论，不是矛盾，是时点不同。**
- `gork` 报告新增了 `review` 报告没有的宿主层发现（P0-1 看门狗中止后不触发切换、P0-2 `before_settle` 里调 `compact()` 会取消续跑）。这两条是本轮**最高价值**的发现，因为它们证明 v3 的核心卖点（长任务自动续跑）在真实宿主上不成立。
- `issue` 报告的问题三（完成后清理破坏证据链）我实测复现：对历史任务执行 `task.py check` 现在报 `task: input file missing: .xr-verify/old/preflight-customer-domains.mjs`。

## 3. 问题定义

### 原始描述

> 分析并修复，github action 部署 migrate 失败，阻塞发布。

用户要求：从三份报告中找出**核心**问题（不是全部问题），参考 PStack 设计原则、第一性原理、奥克姆剃刀，产出技术方案。

### 澄清后的问题

真正要解决的不是「修 80 个 bug」，而是：**v3 的 4 条结构不变量被破坏，需要最小改动恢复它们，同时不为了修 bug 而增加新的机制。**

### 目标

- 给出 4 个根因的可执行修复方案，每个方案都能用一条可运行的反例验证。
- 明确指出哪些报告条目**不该修**（死代码、已被覆盖、超出范围），避免把审查清单机械转成开发清单。
- 修复顺序有依赖依据，不是按报告编号排序。

### 非目标

- 本文不实施任何改动；不修改 `skills/x-rail/**`、`scripts/**`、`extensions/**`。
- 不做真实模型回放（`--live`）对照实验；不宣称修完就普遍提速或降低费用。
- 不处理 P2 级杂项（文档措辞、时间戳格式、`--no-backup` 边界），除非它属于 A–D 的下游。
- 不重开已修项；不改历史任务的证据（只读兼容）。

### 成功标准

1. 4 个根因各有**可运行反例**：修复前必红，修复后必绿。
2. 修完不需要手工编辑 `state.md`、不需要删除历史登记、不需要手改 TSV。
3. 安装位置（`skills/x-rail` 软链 vs `extensions/x-rail` 复制）的差异被写清，验证方式不再依赖猜。
4. 剩余未验证项被如实列出，不用「静态检查通过」冒充真实行为已验证。

## 4. 甄别结论

### 4.1 统计

| 分类 | 数量 | 说明 |
|---|---|---|
| 真问题（我复核或机制确认） | 24 | 归入 A/B/C/D 四类 |
| 已被当前提交修掉 | 1 | `gork` M1 |
| 两条报告的重复项 | 12 | 同一缺陷在两份报告各出现一次（编号不同） |
| 该删除而非实现的死代码/假承诺 | 8 | 见 §6.3 |
| 存疑 / 本机未复现 | 3 | 如实标注，不当作已确认 |
| 超出本次范围（P2 杂项、环境差异） | 其余 | 记入附录，不在方案内 |

### 4.2 本机实测（我复核）

在临时目录用真 `xr` 与宿主源码实测，未触碰仓库文件。

| 反例 | 结果 | 对应 |
|---|---|---|
| 改 `--verify true` → `false` 后再 `xr verify` | `VERIFIED ... cached`，新命令**根本没跑** | C |
| `xr done U1` 后 `xr fail U1 --kind net` | `ok fail U1 todo attempts=1`，**终态被打回** | C |
| `verify`（`sleep 3`）执行期间 `xr next` 派发 B | 结束后 `B` 从 `doing` **被覆盖回 `todo`** | B |
| `ACTIVE` 写成 `../../../<repo外目录>` | 仓库外 `RUN.md` 被 `xr status` **改写** | B |
| `xr gate ... --unit G1` 后想解除 | 无 `resolve` 动词；`plan add` 也被拒 → **单元永久阻塞** | D |
| `/usr/bin/python3`（本机 3.9.6）跑 `zip(strict=False)` | `TypeError: zip() takes no keyword arguments` | B |
| 对历史任务 `task.py check` | `input file missing: .xr-verify/old/...`，状态仍是 `done` | C |
| `scripts/test-install-v3.sh` | 输出 `passed`、exit 0 —— 但断言的是**不存在的路径** | C（假通过） |
| `bash -c 'set -e; [[ -f /nonexistent ]]; echo REACHED'` | 打印 `REACHED`，**裸 `[[ ]]` 不触发 `set -e`** | C（假通过成因） |

**注**：8 并发 `xr next` 在本机**未复现**重复派发（概率性竞争窗口）；机制上确定存在（`cmd_next` 读全表 → 改 → 整表覆写，无锁），且 lost update 已确定性复现。

## 5. 核心问题

### 5.1 第一性原理：v3 的 4 条不变量

从 `v3-goal` 与 `SKILL.md` 抽取，v3 的全部设计服务于 4 条不变量。缺陷不该按「文件」或「严重度」分类，而该问：**哪条不变量被破坏了。**

| 编号 | 不变量 | 来源承诺 |
|---|---|---|
| I1 | 状态在磁盘，会话只是执行器，可换模型、可压缩、可崩溃 | 03 §1「换模型、压缩、崩溃都不影响状态」 |
| I2 | 完成必须由**当前有效**的证据支撑 | v3-goal §八；README「没有证据不能声称完成」 |
| I3 | 状态只有**一个**真相源 | 03 §3「状态文件唯一真相」；DECISIONS C5「只由 xr 写」 |
| I4 | 规则少、硬、可检查；按交付结果分流 | 03 §1「规则少、硬、可检查」；§1.3 |

四个报告里的 80 条，全部落在「破坏 I1 / I2 / I3 / I4」四类。这就是为什么它们看起来多、修起来少。

---

### 5.2 核心问题 A：宿主控制层有两个互不通气的司机

**破坏 I1。**

#### 现状（源码或宿主源码确认）

v3 用两个独立扩展 `x-failover.ts` 与 `x-run-guard.ts`，都挂在宿主同一批生命周期事件上。宿主的两条语义使这种分工不可靠：

1. `runner.js:775-778`：`entries = handlerResult.entries` —— **整体替换**，不是追加；`continue` 取最后一次赋值。两个扩展各返回一条续跑消息，只能活一条。
2. `loader.js:477-480`：`moduleCache: false` —— 每个扩展各拿一份独立模块实例。`watchdog.ts` 里 `markWatchdog()` 改的变量，另一个扩展的 `takeWatchdog()` **永远读不到**。
3. `agent-session.js:1426`：`if (this._agentRunAbortRequested || !(await this._runBeforeSettleBoundary())) break;` —— `ctx.abort()` 之后 `agent_before_settle` **根本不会触发**，所以「看门狗 abort → 切换模型」这条链一次都不会执行。
4. `agent-session.js:2202` + `1547-1548`：`compact()` 第一步 `await this.abort()`，abort 期间置 `_abortDuringBeforeSettle`，随后 `return false` 丢弃扩展的 `continue: true`。所以**在 `before_settle` 里调 `ctx.compact()`，续跑必丢**。而 `xr done` 写出的三个边界标志恒为 `false`，`boundaryDecision` 恒返回 `compact` → **每个单元边界都停**。

`x-failover.ts:70` 的 `located?.id ?? "session"` 让所有无 run 会话共用同一个永不重置的记忆桶，第 3 次失败后**永久不再切换**。

#### 根因（第一性原理）

**控制平面被两个无协调的写入者共享，且通信方式（模块级变量）在宿主的模块隔离下不成立。**

不是「少了 6 个 if」，是「两个司机同一个方向盘」。按 PStack `principle-separate-before-serializing-shared-state`：**先问能不能消除共享，而不是给共享加锁。** 这里共享目标是「agent 生命周期事件」和「扩展内状态」，两者都能通过「合并成一个扩展」直接消除。

#### PStack 对照

- `principle-separate-before-serializing-shared-state`：默认消除共享写目标；「需要加锁」是设计异味。
- `principle-one-writer-per-worktree`（orchestrate 角色段）：一个写入者。
- `orchestrate` 的「Completions are queue events, not interrupts」：控制决策应在一处顺序执行。

#### 最小修复（奥克姆：合并，不新增机制）

| 步骤 | 做法 | 为什么最小 |
|---|---|---|
| A1 | 两个扩展合并为**一个入口**（`x-failover.ts` 保留文件，内部 import `run-guard` 的逻辑；或新建 `x-rail.ts` 并只声明一个清单入口） | 消除 runner 的 entries 覆盖、消除 moduleCache 隔离、消除双 nonce |
| A2 | 一个 `agent_before_settle` handler，**固定顺序**：先故障决策（分类→熔断→切换）→ 再续跑/边界决策；返回**一个** `entries` 数组 | 顺序是显式的，不靠宿主语义 |
| A3 | 边界压缩改为返回 `CompactionEntryDraft`（`{type:"compaction", summary, firstKeptEntryId}`），**不再调 `ctx.compact()`** | 宿主已内置该能力（`types.d.ts:770-777`），与 `continue: true` 可共存 |
| A4 | 看门狗不再走 `abort()` + 等 `before_settle`。合并后改为：达到阈值时直接在 handler 内决策；若必须中止当前轮，则在 `agent_settled` 里用 `pi.sendMessage(..., {triggerTurn:true})` 发起续跑（宿主 `_deferredSettledActions` 正好支持，`agent-session.js:1837-1841`） | 用宿主已支持的 deferred settled action，不自建队列 |
| A5 | 无 active run 时**不落盘**：改用进程内记忆（重启即清）；有 run 时仍按 run id 落盘 | 普通对话本来就不需要跨会话故障记忆；同时止住 `state.runs` 无限增长 |
| A6 | 删除死代码：`applyProbe`（无调用方）、`X_FAILOVER_PROBE` 分支、`boundaryDecision` 的 `new-session`/`subagent`（扩展无法新建会话）、`subagent.ts` 的 `concurrencyLimits/dispatchModel/reviewerFamily`（无运行时消费者）或明确改为「提示词约定」并移出代码 | 承诺了但做不到的分支，删掉比实现便宜 |

#### 备选与取舍

| 方案 | 优点 | 代价 | 取舍 |
|---|---|---|---|
| **A-合并（推荐）** | 根治覆盖与隔离问题；handler 顺序显式 | 单文件变大；一个扩展加载失败影响面变大 | 选它：覆盖面窄，且加载失败可由 `install.sh` 的 manifest 只声明一个入口来兜住 |
| A-保留两个 + `pi.events` 通信 | 文件职责不变 | 仍共享同一事件与 entries；要新增通信协议与状态同步 | 放弃：保留共享再加协调层，违反奥克姆 |
| A-只保留 x-run-guard，failover 并入 | 与 A-合并等价，更激进 | 同上 | 可选，若合并后文件仍可读，等价于 A |

---

### 5.3 核心问题 B：磁盘账本「读整本改整本」

**破坏 I3。**

#### 现状（我复核）

| 位置 | 事实 |
|---|---|
| `xr:79-83` | `write_tsv` = `path.write_text(...)`，截断后写，**无 temp、无 fsync、无 `os.replace`** |
| `xr:372-445` | 所有命令都是「读全表 → 改 → 整表覆写」 |
| `xr:412-445` | `cmd_verify` 在**执行外部命令期间**持有读到的旧 rows，命令结束后整表写回 → 期间任何其他写入被覆盖（我实测确认） |
| `xr:99-101` | `run_dir` 不校验 run id；`run-files.ts:12-16` 同构 → `ACTIVE` 被污染即可写到仓库外（我实测确认仓库外 `RUN.md` 被改写） |
| `store.ts:33-38` | tmp 名固定 `${file}.tmp` + `renameSync`，无锁 |
| `frontier.py:19` | `zip(a, b, strict=False)` 需 Python ≥ 3.10；本机 `/usr/bin/python3` 是 3.9.6 → `TypeError`（我实测确认） |

**同仓已有正确实现**：`coordination.py:71-80` 使用 `temp + os.fsync + os.replace`。

#### 根因

**写路径没有最小化共享窗口，也没有原子性。** 单表状态本身是合理设计（I3 要求唯一真相源），所以不能靠拆分消除共享——这一步才该「串行化」，但要按正确顺序做两件事：先**缩小窗口**，再**加锁**。

#### PStack 对照

- `principle-separate-before-serializing-shared-state`：单一权威对象时才用锁，且要「结构化」而不是约定。
- `orch` 的 `store.ts`：写锁 + 临时文件改名 + **失活进程锁恢复**。「连锁都有现成做法可抄，不要发明。」
- `principle-make-operations-idempotent`：中断后能收敛，不是盲目重试。

#### 最小修复

| 步骤 | 做法 | 为什么最小 |
|---|---|---|
| B1 | 所有写走 `temp（带 pid+随机后缀）→ fsync → os.replace`。直接复刻 `coordination.py:71-80` | 复用同仓既有实现，零新依赖 |
| B2 | `cmd_verify` 改为：执行命令 → **重新加锁、重新读、再写**。绝不在执行外部命令期间持有旧 rows | 这是 lost update 的确定成因，改动局限在单函数 |
| B3 | `.work-docs/runs/<id>/.lock` 上 `fcntl.flock`（标准库，macOS 可用）包住「读-改-写」临界区 | 按 PStack 顺序，窗口缩小后仍需串行化才完整；`fcntl` 是标准库，不引 `proper-lockfile` |
| B4 | `run_dir` 用 `SLUG_RE` + 时间戳格式校验 run id，并断言 `path.resolve()` 落在 `.work-docs/runs` 之下；`xr import` 的 `task_id` 同法校验 | 边界校验，属于「永远不能省」的那一类 |
| B5 | `store.ts` tmp 名加 pid+随机；无 run 时不落盘（见 A5，同时消掉这条的争用来源） | 与 A5 合并，避免两处各修一遍 |
| B6 | `frontier.py:19` 去掉 `strict=False`（它本就是默认行为）；`xr` 开头检查 Python ≥ 3.10 并给可读提示 | 去掉一个关键字即恢复 3.9 兼容；版本检查防其他 3.10 语法 |

#### 备选与取舍

| 方案 | 优点 | 代价 | 取舍 |
|---|---|---|---|
| **B-缩小窗口 + flock（推荐）** | 用标准库；复刻同仓做法；同时解决丢更新与毁账 | macOS only（其他平台需降级） | 选它：项目当前只跑 macOS（README 已写明） |
| B-只加 flock，不改 verify 读写顺序 | 改动更小 | 仍持有旧 rows，锁内写回旧快照照样丢数据 | 放弃：没解决根因 |
| B-改用 SQLite 替 TSV | 天然事务 | 违反「零新依赖」；`xr` 全部动词重写 | 放弃：YAGNI，且巡检可读性下降 |
| B-每个单元独立文件，读时聚合 | 天然无共享写 | units.tsv 是 `xr next` 的 frontier 输入，聚合会破坏单表语义 | 放弃：与 I3 冲突 |

---

### 5.4 核心问题 C：完成门认「文件指纹」不认「判据」

**破坏 I2。**

#### 现状（我复核）

| 位置 | 事实 |
|---|---|
| `xr:419` | 缓存键只有 `(unit, tree_hash, verdict=VERIFIED)`，**不含 `verify_cmd`** → 改判据仍命中缓存（我实测确认） |
| `xr:453-470` | `cmd_done` 只查 ledger，不检查当前状态是否是 `doing`/`verifying` |
| `xr:29` | `TERMINAL = {"done", "abandoned"}` **定义后全文件再无引用**；`cmd_fail`/`cmd_gate`/`cmd_plan_add` 都没有终态守卫 → `done` 可被 `fail` 打回（我实测确认） |
| `xr:177-195` | scope 下无文件时 `tree_hash` 返回 `sha256("")` 前缀 → 空 scope 也能 VERIFIED |
| `xr:680` | `if not cycles(rows): save_units(rows)` —— 无 `else`，失败时**静默不保存但仍打印成功** |
| `xr:668-686` | `xr import` 给导入单元写死 `verify_cmd = "true"` → 给 done 门开后门 |
| `xr:523-548` | gate 只有新增，**无 resolve/close**；`gates.md` 只追加 `status: open`（我实测确认） |
| `task_checks.py:673` / `:504` / `:320` | 契约修订后旧证据按 revision 失效，但**没有合法修订入口** → 逼迫手工改 `state.md`（issue 报告问题五） |

#### 根因（第一性原理）

**完成门的「键」选错了。** 它绑定的是「文件树哈希」，而证据真正要证明的是「**这条判据**在这个版本上被执行并通过」。判据变了（`verify_cmd` 从 `true` 改成 `false`）、状态非法（`done` 被改写）、范围为空（没有文件也算通过），都不该继续被认作完成。

第二层根因：**契约修订缺少合法路径**，检查器严格但不给出路，只能手工改状态 —— 这会把「证据链」变成「表演性证据链」。

#### PStack 对照

- `principle-prove-it-works`：核对实际值、实际产物；「编译通过、文件新、日志写了完成，都不等于用户结果成立」。
- `shipping` 的 ledger：**新 head SHA 作废旧行**，「A new head SHA voids the row, so re-verify after restack」。xr 的等价物是「新判据作废旧行」。
- `store-ledger`：「同一键的新登记替换原行」——但**键必须包含判据**。
- `principle-encode-lessons-in-structure`：把重复教训放进结构（这里就是「缓存键」），而不是加一句提醒。

#### 最小修复

| 步骤 | 做法 | 为什么最小 |
|---|---|---|
| C1 | 缓存键加入 `sha256(verify_cmd)`；ledger 增加 `cmd_hash` 列，旧行缺列时视为未通过 | 一处键定义改动，向后兼容读 |
| C2 | `done`/`fail`/`plan add`/`gate` 入口统一加 `if row["state"] in TERMINAL: die(...)`，把**已定义的** `TERMINAL` 接上；另留显式 `xr reopen <id>` 作为唯一合法重开路径 | 删掉「已定义未接线」的悬空常量，不是新增机制 |
| C3 | `scope` 为空或匹配 0 文件时直接拒绝，不返回空摘要 | 拒绝假通过，属于边界校验 |
| C4 | `import` 加 `else: die(...)`；`verify_cmd` 不再写 `"true"`，改为 `"false"` 并标注需重写判据 | 让导入的单元**必须**重新写判据，不能继承一个能过门的假命令 |
| C5 | 新增 `xr gate resolve G<n> --answer ...｜--default`：把 `gates.md` 状态改为 resolved，关联单元恢复 `todo` | 补齐状态机的缺失转移，不新增状态种类 |
| C6 | `task.py` 新增 `revise <task-dir>`：bump `contract_revision`、同步 `state.md` 的 revision/fingerprint、把受影响证据标为 stale 并保留历史行、允许重验 | 把「手工改状态」变成「一条命令」，并且它自己也要留 audit |
| C7 | `test-install-v3.sh`：断言路径改为 `extensions/x-rail/...`，所有裸 `[[ ]]` 改成 `[[ ... ]] || { echo fail; exit 1; }`；把 `test-xr`/`test-failover`/`typecheck-extensions`/`test-install-v3` 纳入 `check-repo.sh` | 去掉假通过；让回归被门禁看见。注意：**当前 `test-install-v3.sh` 在本机 exit 0「passed」，原因是断言路径错 + bash 3.2 裸 `[[ ]]` 不触发 `set -e`，两个缺陷叠加**；在 bash ≥ 4 上它会真实失败。两条都要修 |

#### 备选与取舍

| 方案 | 优点 | 代价 | 取舍 |
|---|---|---|---|
| **C-补键 + 接线 TERMINAL + 加 revise（推荐）** | 修复点在门本身，用户无需改习惯 | `revise` 是新命令 | 选它：`revise` 是**补缺口**不是扩能力，缺它必然导致手工改状态 |
| C-取消 verify 缓存，每次重跑 | 最简单，不可能误命中 | 长任务每次 verify 都重跑，成本与时间上升 | 不选，但保留为逃生开关：`xr verify --no-cache` |
| C-删掉 `TERMINAL` 常量 | 消除悬空定义 | 不解决「done 可被改写」 | 放弃：那是删症状 |
| C-让 gate 单元可以被 `plan add` 覆盖 | 少一个动词 | blocked 单元被静默替换，丢掉「为什么阻塞」 | 放弃：`resolve` 语义更清楚 |

---

### 5.5 核心问题 D：两套流程并行，自动续跑越权

**破坏 I4。**

#### 现状（我复核或机制确认）

| 位置 | 事实 |
|---|---|
| `SKILL.md:11-30` | 入口同时指向两套模型：`routing` → `playbooks/*`（task.py 证据模式），`workflow` → `stages/*` + `xr`；**没有写「什么时候读 stages、什么时候读 playbook」** |
| `skills/x-rail/**` Markdown 总量 | 109,854 → 136,461 字节（+24%），同时并行存在两套任务模型 |
| `stages/execute.md:9` vs `modules/work-items.md:105` | 子代理时限两套：45/25/15 分钟 vs 「不另设运行倒计时」 |
| `stages/plan.md:8` vs `playbooks/exec.md:32` | 默认委派两套：<5 单元 main vs 默认委派 |
| `x-run-guard.ts:90-145` + `guard-core.ts:25-43` | 只要 `.work-docs/runs/ACTIVE` 存在且未完成，**每个 completed 回合都强制续跑**，包括模型向用户提问（Frame 阶段的 grilling 正要求提问） |
| `run-files.ts:60` | `gateOpen = /status: open/.test(gates)`，而全仓无关闭路径 → 一旦 gate 打开且剩余单元全 blocked，`x-run-guard` 永久 `stop + handoff` |
| `ACTIVE` | 无任何 verb 能清除；run 完成后依然存在 → 每个新会话都提示「有未完成的 run」 |
| `guard-core.ts:99` | 提示用户输入 `/x-rail resume`，但**没有注册该命令** |
| `contract.md` 的 `cost_control: unlimited` | 只检查字段非空，不校验授权语义 → 「分析并修复」被解释为取消成本限制（issue 报告问题四） |

#### 根因（第一性原理）

**控制平面没有单一权威，且「参与 run」与「向用户提问」没有区分。**

- 文档层：两套模型并行，模型在同名语义（`plan`/`review`/`verification`）上随机选择。
- 扩展层：run-guard 把「存在 active run」当成「必须自主推进」，而 Frame/Review 阶段**本来就该问人**。
- 授权层：把「获准完成工作」和「获准取消资源限制」混成一个判断。

#### PStack 对照

- 入口按交付性质分流，但每条路**只有一套权威规则**；x-rail 现在是两条路并行。
- `orchestrate` 的 escalation 清单：明确「什么才到人」（不可逆、产品/偏好判断、与观测冲突的 standing order、真死路）；「frontier nudges、retries、CI flake」不到人。run-guard 现在把「模型提问」也算成「需要续跑」，正好相反。
- `principle-never-block-on-the-human`：自主执行 + gate 带默认值继续推进 —— 但**前提是 gate 有出路**（`resolve`）。
- `principle-laziness-protocol`：consolidate decisions，「不要在多处重复同一个选择」。

#### 最小修复

| 步骤 | 做法 | 为什么最小 |
|---|---|---|
| D1 | `SKILL.md` 写一条**二选一判据**：跨会话/外部等待/必需依赖汇总/敏感动作 → `stages` + `xr`；其余 → `playbooks` + `task.py`。同名语义各保留一处，其余改为路径引用 | 入口只加一条判据，不改路由结构 |
| D2 | 三处矛盾规则各留一处为准（时限以 `stages/execute.md` 为准、委派以 `DECISIONS C1` 为准、失败阈值以 `references/failure-modes.md` 为准），其余改为引用 | 删重复，不加新规则 |
| D3 | run-guard 续跑加门控：① 只在**本会话发起或恢复过该 run** 时续跑（`session_start` 时 `pi.appendEntry` 写绑定标记）；② 最后一条 assistant 消息是**向用户提问**时跳过续跑；③ 子代理进程用 `X_RAIL_SUBAGENT=1` 禁用 | 三个门控都是「不加机制」的收窄 |
| D4 | 新增 `xr close`：清除 `ACTIVE`（写 `run closed` 标记，保留目录与证据）；`xr done` 全部单元完成时提示执行它 | 补上 ACTIVE 的唯一合法出路 |
| D5 | 「删除数据、强推、生产迁移、花钱、对外发布、范围变更」之外，`cost_control: unlimited` 只在原话匹配「解除成本限制/不限成本/不计成本」时接受；否则 `start` 拒绝 unlimited 并回落默认预算 | 收紧而非新解析器：关键词变窄 + 必须引用原话 |
| D6 | 入口删掉与 `modules/` 重复的 8 段（`budget`/`verification`/`recovery` 等），只留路由与硬规则；`references/`/`templates/` 里 5 个孤儿文件补索引或删除 | 直接减总量，回应「+24% 假优化」的验收失分 |
| D7 | `guard-core.ts` 的 `resumeHint` 改为「读 `.work-docs/runs/<id>/capsule.md` + `xr status`」；或注册真实 `/x-rail resume` | 消除不存在的命令提示 |

#### 备选与取舍

| 方案 | 优点 | 代价 | 取舍 |
|---|---|---|---|
| **D-加判据 + 收窄续跑 + 补 close（推荐）** | 三条都不新增机制；入口变小 | 需要一次入口改写 | 选它 |
| D-废弃 `playbooks`/`task.py`，全走 `xr` | 只有一套模型，最彻底 | 破坏历史任务只读兼容；`task.py` 的 15 个子命令与 CI 仍被依赖 | 放弃：DECISIONS C3 已裁决 task.py 保留为可选检查器 |
| D-保留两套，靠提示词区分 | 零代码改动 | 「模型必须记得去做」正是 v3 要消除的东西（03 §1） | 放弃：与设计原则冲突 |

## 6. 方案

### 6.1 修复顺序（有依赖依据）

```
第一批（互相独立，可并行）
  C1 C2 C3 C4 C5 C7   ← 完成门与假通过，改动小、收益直接
  B4 B6               ← 边界校验与 3.9 兼容
第二批（依赖第一批的 verify 语义稳定）
  B1 B2 B3 B5         ← 原子写 + 缩窗 + flock
第三批（依赖 B3 的锁与 C6 的修订入口）
  C6                  ← task.py revise
第四批（改动面最大，需在 A 之后）
  A1 A2 A3 A4 A5 A6   ← 扩展合并
  D1 D2 D3 D4 D5 D6 D7
```

理由：A 与 D 会改动 `agent_before_settle` 的**唯一 handler**，而 C 的 `verify` 语义与 B 的锁会改变 handler 读取的状态。先把状态层做稳，再做控制层，避免「在流沙上盖楼」。

### 6.2 每项的验收反例

每条都必须**修复前必红、修复后必绿**，用可运行命令，不靠描述。

| 项 | 反例命令 | 期望 |
|---|---|---|
| C1 | 改 `--verify false` 后 `xr verify <id>` | 必须**真的执行** `false` 并 FAILED，不能 cached |
| C2 | `xr done <id>` 后 `xr fail <id> --kind net` | 必须拒绝；`xr reopen <id>` 才允许 |
| C3 | `plan add` 后删掉 scope 内文件再 `verify` | 必须拒绝，不产出 VERIFIED |
| C4 | 构造 `depends=w9` 的旧任务做 `xr import` | 必须非 0 退出且不打印 `ok import` |
| C5 | `gate ... --unit G1` 后 `gate resolve G1 --default` | 单元恢复 `todo`，`gates.md` 变为 resolved |
| C6 | 已有通过证据的任务改契约后 `task.py revise` | 无须手改 `state.md`；受影响证据标 stale；可重验 |
| C7 | `bash scripts/test-install-v3.sh` | 断言落在真实安装路径；裸 `[[ ]]` 全改；故意写错路径时**必须**失败 |
| B1 | 写到一半 `kill -9` | `units.tsv` 保留上一完整版本，不出现半截文件 |
| B2 | `verify`（`sleep 3`）期间 `xr next` | 结束后新派发的单元**仍是 doing**（不得退回 todo） |
| B3 | 20 并发 `xr next` | 同一单元只被派发一次；无 lost update |
| B4 | `ACTIVE` 写成 `../../../x` | 必须拒绝并给可读错误，不写仓库外 |
| B6 | `/usr/bin/python3 xr next`（3.9） | 给出「需要 Python ≥ 3.10」提示，不抛 traceback |
| A | 挂起主 provider，等看门狗触发 | 请求落到 bai，且**发生续跑**（当前是 abort 后什么都不做） |
| A3 | 单元边界后 | 压缩与续跑**同时**生效，不在每个边界停 |
| A5 | 新会话连续 3 次故障 | 不再出现「永久 handoff」 |
| D3 | 存在 ACTIVE、模型向用户提问 | **不注入**续跑消息 |
| D4 | `xr close` | `ACTIVE` 清除；新会话不再提示未完成 |
| D5 | 契约写 `cost_control: unlimited` + 「分析并修复」 | `start` 拒绝 unlimited |

### 6.3 该删除而不是实现（奥克姆）

| 位置 | 现状 | 处置 |
|---|---|---|
| `boundaryDecision` 的 `new-session` | 扩展无法以编程方式新建会话 | 删除分支（`x-run-guard.ts:130` 已把它映射成 `compact`，等于死代码） |
| `boundaryDecision` 的 `subagent` | 边界决策处不派子代理 | 删除，或明确写「由 Execute 卡的派发规则承担」 |
| `boundaryDecision` 的三个输入标志 | `xr done` 恒写 `false` | 删除三个标志与 `pending-boundary.json` 的这三个字段，`boundaryDecision` 只按上下文决定 |
| `applyProbe` / `X_FAILOVER_PROBE` | 无调用方 | 删除（`PROBE_SUCCESSES`、`consecutiveProbeOk` 一并删） |
| `subagent.ts` 的 `concurrencyLimits`/`dispatchModel`/`reviewerFamily` | 只有测试引用 | 删除，或在文档写明「提示词约定」并移出运行时代码 |
| `TERMINAL` 常量 | 定义未接线 | **接线**（C2），不是删除 |
| `references/`、`templates/` 的 5 个孤儿文件 | 入口不可达 | 补入口索引或删除 |
| `SKILL.md` 与 `modules/` 重复的 8 段 | 入口体积重复 | 删除重复，保留一处 |

### 6.4 不做什么（范围外）

- 不跑真实模型对照实验，不宣称提速或省钱。
- 不迁移、不改写历史任务证据；只补合法修订入口。
- 不删除旧 `playbooks`/`task.py`；保留为可选检查器。
- 不动 P2 杂项（时间戳格式、`--no-backup` 细节、两套 install 脚本的文档），除非被 A–D 顺带覆盖。
- 不改用户的 `~/.pi` 配置、不安装、不推送、不部署。

## 7. 未解决问题与候选盲点

| 项 | 影响 | 状态 | 下一步验证 |
|---|---|---|---|
| 切换到 bai 后 `pi.sendMessage(..., {triggerTurn:true})` 是否真能发起续跑 | 高（A4 依赖它） | 候选盲点，仅从宿主源码推断（`_deferredSettledActions`） | 最小扩展探针实测 |
| `ctx` 上取 sessionId 的确切途径 | 中（A5 的备选实现） | 已知未知 | 读 `ReadonlySessionManager` |
| `CompactionEntryDraft` 与 `continue: true` 同时返回是否被接受 | 高（A3 依赖它） | 候选盲点，类型定义显示支持（`BoundaryState` 同时有 `entries` 与 `continue`） | 端到端实测 |
| 并发 `xr next` 重复派发的概率窗口 | 中 | 本机 8 并发未复现；机制确定 | 20 并发 + 插桩计时 |
| `xr import` task_id 逃逸出仓库 | 中 | 机制确认（无校验），本机层级不足未复现 | 用 `../../../` 复现 |
| `pi-subagents` 子进程是否加载全局 extensions | 中（D3③ 的前提） | 已知未知 | 子进程探针 |
| 无 run 会话改用进程内记忆后，跨压缩的故障记忆是否足够 | 中 | 设计假设 | 压缩后回放 |
| 扩展合并后单文件体积与可读性 | 低 | 设计取舍 | 合并后量体量，超限再拆内部模块（不是拆扩展） |

## 8. 决策记录

| 决策 | 理由 | 放弃的备选 | 日期 |
|---|---|---|---|
| 按 4 个根因修，不按 80 条平铺 | 第一性原理：80 条都落在 4 条不变量上 | 逐条修 | 2026-10-17 |
| A 采用「合并扩展」而非「加通信层」 | PStack separate-before-serializing：先消除共享 | `pi.events`、状态文件通信 | 2026-10-17 |
| B 采用「缩小窗口 + flock」，不改 SQLite | 复用同仓 `coordination.py` 既有做法；零新依赖 | SQLite、仅加锁 | 2026-10-17 |
| C 采用「补缓存键 + 接线 TERMINAL + 加 revise」 | 修在门本身；`revise` 是补缺口 | 取消缓存、覆盖 blocked 单元 | 2026-10-17 |
| D 保留两套模型但加二选一判据 | 历史兼容要求保留 task.py（DECISIONS C3） | 全走 xr、靠提示词区分 | 2026-10-17 |
| 死代码删除而非实现 | 奥克姆：做不到的承诺，删掉比实现便宜 | 实现 applyProbe/新会话 | 2026-10-17 |
| 修复顺序：状态层 → 完成门 → 控制层 | 避免在流沙上盖楼 | 按报告严重度排序 | 2026-10-17 |

## 9. 下一步行动

| 阶段 | 行动 | 验证产物 | 优先级 |
|---|---|---|---|
| 1 | C1–C5、C7 实施 + 反例测试 | 每个反例「前红后绿」记录 | 高 |
| 1 | B4、B6 实施 | 逃逸与 3.9 反例 | 高 |
| 2 | 宿主探针实测（§7 前三项） | 探针脚本与原始输出 | 高 |
| 2 | B1–B3、B5 实施 | kill -9 与并发反例 | 高 |
| 3 | C6 `task.py revise` 实施 | 对历史任务做一次只读演练（不写） | 中 |
| 4 | A1–A6 扩展合并 | 挂起 → 切换 + 续跑端到端 | 高 |
| 4 | D1–D7 入口与门控 | 提问不续跑、`xr close`、unlimited 拒绝 | 中 |
| 5 | 把 v3 测试纳入 `check-repo.sh`，补扩展 handler 级集成测试 | `check-repo.sh` 覆盖 v3 | 中 |

## 10. 实施状态（2026-10-18）

### 已实施

- C：验证账本增加验证命令哈希；`done` 只接受当前文件和当前验证命令的通过证据；终态禁止直接 `fail`，通过 `xr reopen` 合法重开；空 scope 拒绝；`gate-resolve` 补齐 gate 出口；导入单元不再使用永远通过的 `true`；安装测试改为检查实际复制路径并拒绝第二扩展入口；新增 `task.py revise`，保留历史快照、同步状态并将旧证据置为 `not_run`。
- B：TSV 和关键文本使用临时文件、`fsync`、`os.replace`；`xr` 的 run 读改写使用 `.lock`；验证外部命令期间释放锁，完成后重新读取 units；run id、ACTIVE 路径和导入 task id 做边界校验；移除 Python 3.10 的 `zip(strict=False)`。
- A：`x-failover.ts` 成为唯一宿主入口，内部注册 run guard 生命周期；看门狗在 settled 阶段切换并通过 `triggerTurn` 发起续跑；边界处理不再直接调用 `compact()`；无 active run 不写故障记忆；扩展状态和 guard 状态原子写入。
- D：技能入口增加两套流程的选择判据；run guard 只绑定当前会话已发现的 run、跳过子代理和明显提问回合；交接提示改为真实的 `capsule + xr status`；新增 `xr close` 清除 ACTIVE；无 active run 时保留当前会话内故障记忆，并在新会话重置。

### 已验证

实际运行并通过：`python3 scripts/test-xr.py`（6 项）、`python3 scripts/test-task-checks.py`（72 项）、`bash scripts/typecheck-extensions.sh`、`bash scripts/test-failover.sh`（failover 与 mock26）、`bash scripts/test-install-v3.sh`、Python 编译检查、`git diff --check`。LSP 对 TypeScript 修改文件未报告错误；Python `xr` 无配置 LSP，已用编译和公开测试覆盖。

### 未验证与剩余盲点

- 尚未做真实 pi 进程端到端探针，因此 `sendMessage(..., { triggerTurn: true })` 看门狗续跑、单一入口下 `agent_before_settle` 返回消息与宿主实际请求链仍是类型和源码级确认，不写成真实运行已确认。
- 尚未运行全量仓库测试、独立 `code-review`，也尚未提交。

## 11. 附录

### 10.1 术语

| 词 | 大白话 |
|---|---|
| 扩展（extension） | 装在 pi 里的后台插件，能在「模型回答完」这类事件上插手 |
| 宿主 | pi 本体；扩展跑在它提供的生命周期里 |
| `agent_before_settle` | 「这一轮要结束了，还有话要说吗」这个钩子，扩展可在这里追加消息或要求继续 |
| `xr` | v3 的记账命令；状态写在磁盘的 TSV 里 |
| run / unit | 一次长任务 / 任务里可单独验证的一小块 |
| ledger | 验证账本；记「哪个单元、哪份文件、哪条命令、什么结果」 |
| gate | 需要人拍板但带默认值的问题 |
| 熔断（breaker） | 主模型连续出错就暂时不用它 |
| failover / failback | 切到备用模型 / 切回主模型 |
| capsule | 不超过 2KB 的恢复说明，由脚本生成，不用大模型写 |

### 10.2 证据索引

**本次实测**（临时目录，未触碰仓库）：

- `xr` verify 缓存、done/fail 终态、verify 期间 lost update、run_dir 逃逸、gate 无出路：`skills/x-rail/scripts/xr:29,79-83,99-101,157,412-445,419,453-470,477,523-548,680`
- `store.ts:33-38` tmp 名；`run-files.ts:12-16,60`；`frontier.py:19`
- 宿主：`@earendil-works/pi-coding-agent@1.3.0` 的 `dist/core/agent-session.js:1426,1547-1548,1837-1841,2202`、`dist/core/extensions/runner.js:775-778`、`dist/core/extensions/loader.js:477-480`、`dist/core/extensions/types.d.ts:770-777,797-805`
- 环境：Node v22.22.2、`python3` 3.13.13、`/usr/bin/python3` 3.9.6、`bash` 3.2.57
- 安装形态：`~/.pi/agent/skills/x-rail` → 软链到本 worktree（改源码立即生效）；`~/.pi/agent/extensions/x-rail` → **真实目录复制**（改扩展必须重跑 `install.sh`）

**引报告、本次未复跑**：`gork` 的端到端 pi 复现（P0-1 证据 1、P0-2、P0-3 三次会话、P1-10 三进程写）、`review` 的 20 并发 `next`。这些已在 §4.2 明确标注。

### 10.3 报告条目对照

详见[issue-matrix.md](issue-matrix.md)：两份报告的编号 → 4 个根因的映射，以及「已修 / 重复 / 删除 / 存疑」的逐条判定。
