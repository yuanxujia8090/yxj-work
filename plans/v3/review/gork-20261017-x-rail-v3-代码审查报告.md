# x-rail v3 分支代码审查报告

- 审查对象：x-rail `v3` 分支，提交 `d6fc6a1`（`git log main..v3` 共 32 个提交，80 个文件，+6825/−165，不含 plans/ 和 lock 文件）
- 审查日期：2026-10-17（Asia/Shanghai）
- 方法：独立阅读代码，对照 `@earendil-works/pi-coding-agent@1.3.0` 的真实源码，并用真实 pi 1.3.0 + 本地 mock provider 做端到端复现。按要求没有读取、也没有搜索任何既有审查、验证或实现报告。
- 所有复现都在副本上做（`/workspace/v3-cr/run`、`/workspace/v3-cr/run-wd`、`/tmp/xr*`），源码树 `/workspace/v3-cr/tree` 没有改动。

---

## 1. 结论

**不建议合并。** v3 的骨架方向是对的：按结果分流、用 `xr` 记账、阶段卡瘦身、把 provider 错误分类后做熔断和切换。纯函数层也写得干净，测试覆盖了大部分分支。问题在于两个扩展接到 pi 运行时的方式，和 pi 1.3.0 的真实行为对不上，导致几个核心目标在真实运行里达不到。下面四条都已在真实 pi 1.3.0 上复现：(1) 看门狗中止后 `agent_before_settle` 根本不会触发，E5 切换永远不发生；(2) 只要在 `agent_before_settle` 里调用 `ctx.compact()`，pi 就会先 abort，丢掉本次续跑。而 `xr done` 之后每个单元边界都会走到压缩，所以长任务会在每个单元边界停下，跨 provider 的“先压缩再切换”也一样停下；(3) 没有 active run 的会话共用一份全局失败计数，累计两次 failover 之后，以后所有会话都拒绝切换；(4) 分类器只认 `HTTP 401` 这类写法，而 pi 实际给出的是 `401: {...}`，所以 401/403/429/5xx/`account_pool_forbidden` 都判成 none，不切换。另外，`xr` 没有任何文件锁，并发 `xr next` 会把同一个单元派给两个子代理；verify 缓存不认命令，改了验证命令仍然命中旧的 VERIFIED；v3 自带的 `test-install-v3.sh` 在 HEAD 上是失败的。建议先修完 P0 和大部分 P1，补上扩展处理器级别的测试（可以复用本报告的 mock provider 套件），再考虑合并。

---

## 2. 审查范围与方法

**范围（按权重）**

1. `skills/x-rail/extensions/*.ts`：x-failover.ts、x-run-guard.ts，以及 classify/breaker/switch/compat/failback/store/run-files/guard-core/watchdog/subagent/constants
2. `skills/x-rail/scripts/xr` 及其依赖 `frontier.py`（xr 在导入时还会连带加载 coordination/task_checks/work_items），以及 `self_check.py`
3. `skills/x-rail/install.sh`，以及它和旧的 `scripts/install.sh` 之间的关系
4. `SKILL.md`、`stages/*.md`、`references/*.md`、`config/examples/*`，与 x-handoff/x-worktree/x-self-check 做文档对代码的交叉核对
5. 测试与检查脚本：`test-xr.py`、`failover.test.ts`、`test-mock26.mjs`、`test-install-v3.sh`、`typecheck-extensions.sh`、`check-repo.sh`，以及其余 scripts/test-*

**方法**

- 逐文件读代码，并对照 pi 1.3.0 的 `dist/core/agent-session.js`、`dist/core/extensions/runner.js`、`loader.js`、`types.d.ts` 和 `docs/extensions.md`，核对事件语义：`agent_before_settle` 怎样串联、`ctx.compact`/`ctx.abort` 会带来什么副作用、扩展之间怎样隔离。
- **端到端复现台**（`/workspace/v3-cr/e2e/`）：
  - `mock.mjs` 是一个 OpenAI 兼容的 mock 服务，能按脚本返回 HTTP 错误、SSE 成功流或挂起，并把每个请求记到日志；
  - `run.sh` 在临时 HOME 里用 v3 的 `install.sh` 安装，写入 `models.json`（openai26 → 端口 18801，bai → 端口 18802），然后运行真实的 `pi -p --model openai26/gpt-6.1-sol`，再打印 mock 请求日志、`x-failover.json` 和会话 jsonl。
  - pi 用的 Node 是 22.23.3（box 自带的是 Node 20，另行下载了 22）。
- **纯逻辑复现**：`/workspace/v3-cr/repro/logic.ts`、`c2.ts`、`store-race.ts` 直接导入副本里的扩展模块，用 `node --experimental-strip-types` 运行。
- **xr 复现**：在 `/tmp/xr1..xr8` 里用 `python3 xr ...` 直接跑。Python 3.9 的复现用 `uv` 装的 CPython 3.9.25。
- 每条问题都标了 **已复现**（有命令和实际输出）或 **仅代码推断**。

---

## 3. 测试结果

| 测试 / 检查 | 环境 | 结果 | 说明 |
|---|---|---|---|
| `python3 scripts/test-xr.py` | Python 3.13.5 | ✅ 5/5 通过 | |
| 同上 | **Python 3.9.25** | ❌ 1 失败 | `test_overlap_verify_done_and_fail`：`frontier.py:19` 的 `zip(..., strict=False)` 抛 TypeError，见 P1-9。macOS 自带的 `/usr/bin/python3` 是 3.9 系列 |
| `bash scripts/test-failover.sh` | Node 20.19.2（box 自带） | ⚠️ 环境失败 | `node: bad option: --experimental-strip-types`，属于环境原因 |
| 同上 | Node 22.23.3 | ✅ 通过 | `failover tests passed` / `mock26 tests passed`。但这两个测试的有效性有限，见 P2-12 |
| `bash scripts/typecheck-extensions.sh` | Node 20 和 22 | ✅ 通过 | Node 20 下 npm 报 EBADENGINE 警告，不影响结果 |
| `bash scripts/test-install-v3.sh` | bash 5.2 | ❌ **失败（真实缺陷）** | 第 15 行断言 `~/.pi/agent/extensions/x-failover.ts`，但 `decd5c7` 已把扩展改装到 `extensions/x-rail/`，测试没有跟着改。见 P1-11 |
| `bash scripts/check-repo.sh` | | ✅ 通过 | 但它不运行任何 v3 测试（xr/failover/typecheck/install-v3），所以没拦住上面这个失败 |
| `python3 skills/x-rail/scripts/self_check.py` | | ✅ 通过 | `体量通过 入口=4545`，没有指定外部技能目录，跳过了存在性检查 |
| `python3 scripts/test-v3-self-check.py` | | ✅ 3/3 | |
| test-coordination / test-frontier / test-task-checklist / test-repo-boundary / test-self-check / test-work-items / test-task-checks | | ✅ 全部通过 | |
| test-install.sh / test-fixtures.sh / test-contract.sh | | ✅ 通过 | |
| `bash scripts/test-flow.sh` | | ⚠️ 环境失败 | `FileNotFoundError: .../plans/0.0.6/优化方案.md`，因为输入包排除了 plans/ |
| `bash scripts/test-worktree.sh` | | ⚠️ 环境失败 | box 的 `/usr/bin/pnpm` 是 corepack shim，测试设的 `PATH=/usr/bin:/bin` 拿不到“缺 pnpm”的场景。属于环境原因，但也说明这个测试依赖宿主环境 |
| 端到端：openai26 返回 `503 账号池暂无可用账号` | 真实 pi 1.3.0 | ✅ 正常切到 bai 并续跑 | 主路径可用 |
| 端到端：其余场景 | 真实 pi 1.3.0 | ❌ 见 P0-1..P0-4、P1-3、P1-5、P1-6 | |

**汇总：** 仓库自带的测试中，有 1 个真实失败（test-install-v3），3 个因环境失败（Node 版本、plans 缺失、pnpm shim），其余通过。现有测试几乎全部停留在纯函数层，没有一个测试真正驱动 x-failover.ts 或 x-run-guard.ts 的事件处理器。本报告的 P0 全部出在这一层。

---

## 4. 问题清单

### P0：必须修

#### P0-1　看门狗中止后不会发生 E5 切换（设计目标没有实现）　【已复现】

- **位置**：`extensions/x-run-guard.ts:62-83`（看门狗调 `markWatchdog()` 后再 `ctx.abort()`）；`extensions/x-failover.ts:118`（`takeWatchdog()`）；`extensions/watchdog.ts:1-11`；pi `dist/core/agent-session.js:1419,1426`；pi `dist/core/extensions/loader.js:478`
- **现象**：有两个独立原因，任何一个都足以让 E5 失效。
  1. pi 的 `abort()` 会设置 `_agentRunAbortRequested = true`。运行循环 `while (!this._agentRunAbortRequested)` 退出后，第 1426 行 `if (this._agentRunAbortRequested || !(await this._runBeforeSettleBoundary())) break;` 直接跳过了 `agent_before_settle`。x-failover 的分类、熔断和切换都挂在这个事件上，一次都不会执行。
  2. pi 给每个扩展各建一个 jiti 实例，并且设 `moduleCache: false`，所以 x-run-guard 和 x-failover 各拿到一份独立的 `watchdog.ts` 模块。`markWatchdog()` 改的那个变量，`takeWatchdog()` 永远读不到。
- **证据 1**：用副本 `run-wd` 把 `WATCHDOG_MS` 改成 8 秒，让 openai26 挂起，bai 正常：
  ```
  $ SRC=/workspace/v3-cr/run-wd ./run.sh wd '[{"hang":true},{"text":"primary second"}]' '[{"text":"hi from bai"}]'
  pi exit=1
  stderr: Request aborted
  requests: openai26 req#1 model=gpt-6.1-sol ...（没有任何 bai 请求）
  state:（x-failover.json 根本没有生成）
  session: ... message assistant aborted "Request aborted"
  ```
- **证据 2**：两个扩展共享同一个 `flag.ts`，扩展 a 在 session_start 调 `mark()`，扩展 b 在 before_agent_start 调 `take()`：
  ```
  b 看到的 flag = false
  ```
- **影响**：openai26 卡流是主模型最常见的不稳定形式之一。看门狗只会把运行中止掉，不会换模型，也不会续跑。长任务会停下来，等用户手动干预。
- **修复建议**：看门狗不要走 `ctx.abort()` 再指望 before_settle 处理。可以选一种：(a) 在 x-run-guard 的看门狗里直接执行切换逻辑：`pi.setModel(bai)`，然后在 `agent_settled` 里用 `pi.sendUserMessage()` 或 `pi.sendMessage(..., {triggerTurn:true})` 发起续跑；(b) 把两个扩展合并成一个入口，共享内存状态；(c) 跨扩展通信用 `pi.events` 或状态文件，不要用模块级变量。另外要补一个端到端测试：挂起，等看门狗触发，断言请求落到 bai。

#### P0-2　在 `agent_before_settle` 里调用 `ctx.compact()` 会取消续跑：每个单元边界都会停下　【已复现】

- **位置**：`x-run-guard.ts:118-133`（边界压缩）；`x-failover.ts:165`（compact-then-switch）；`x-failover.ts:90`（compact-then-switch-back）；`guard-core.ts:85-88`；`xr:466-471`（`cmd_done` 写出的 pending-boundary 三个标志恒为 false）；pi `agent-session.js:2202,1950,1547`
- **现象**：pi 的 `compact()` 第一步就是 `await this.abort()`，源码注释写着“Manual compaction never retries or continues the interrupted agent turn”。abort 在 before_settle 期间会设置 `_abortDuringBeforeSettle = true`，第 1547 行随后 `return false`，扩展返回的 `continue: true` 就被丢弃了。
  - `xr done` 写出的 `dependsOnReasoning/unrelated/unattended` 恒为 false，`boundaryDecision` 因此恒返回 `"compact"`。结果是**每完成一个单元，自动续跑就终止**。
  - `X_FAILOVER_REPLAY_COMPATIBLE=0` 时，“先压缩再切换”能切到 bai，但不会续跑。
- **证据 A（单元边界）**：
  ```
  # SETUP：xr init；plan U1、U2；next；verify U1；done U1
  $ ./run.sh boundary '[{"text":"U1 完成"}]' '[{"text":"摘要"}]' "继续任务"
  requests: openai26 req#1 ...（只有 1 个请求）
  events:   {"type":"boundary","choice":"compact",...}
            {"type":"resume",...}           ← x-run-guard 以为已经续跑
  session:  ... assistant stop → custom_message x-run-guard（之后没有任何请求）
  ```
- **证据 B（跨 provider 不兼容）**：
  ```
  $ X_FAILOVER_REPLAY_COMPATIBLE=0 ./run.sh compactswitch '[{"status":503,"body":{"error":{"message":"账号池暂无可用账号"}}}]' '[{"text":"hi from bai"}]'
  stdout: （空）  pi exit=0
  requests: 只有 openai26 req#1，没有 bai 请求
  session:  ... custom x-failover → model_change bai → custom_message x-failover（不再续跑）
  ```
  （会话很短，所以压缩本身会因为“session too small”失败，但续跑在 abort 那一步就已经被丢弃，与压缩成败无关。）
- **影响**：v3 的核心卖点是“长任务按单元自动续跑”，这个目标在每个单元边界都会落空。降级路径中的压缩分支也会停住。
- **修复建议**：不要在 before_settle 里调用 `ctx.compact()`。改为返回一个 `CompactionEntryDraft`（`{type:"compaction", summary: 胶囊, firstKeptEntryId}`），pi 的 boundary 机制本身支持在 entries 里提交 compaction，这样能和 `continue: true` 一起生效。或者在 `agent_settled` 之后再压缩，压缩完成后在 `onComplete` 里 `sendMessage({triggerTurn:true})`。同时让 `xr done` 能写出真实的边界标志（例如增加 `--depends-on-reasoning` 参数），否则 `boundaryDecision` 的 continue 和 subagent 分支永远走不到。

#### P0-3　无 run 会话共用一份全局计数：累计两次 failover 后，以后所有会话都拒绝切换　【已复现】

- **位置**：`x-failover.ts:70`（`const runId = located?.id ?? "session"`）、`x-failover.ts:55-64`（只有存在 active run 时才累计工具调用数）、`switch.ts:60-78`（`handoffOrSwitch`）、`store.ts:13-16`（全局文件 `~/.pi/agent/state/x-failover.json`）
- **现象**：没有 active run 时，所有会话都写进同一个 `runs.session`，而且永远不会重置。`toolCallsSinceFailover` 在这种情况下永远是 0，于是第 2 次 failover 后 `failoversWithoutProgress=1`，第 3 次直接判定为 `handoff`（“连续 failover 后没有工具进展”）。哪怕前后隔了几天、中间做了大量工作，结果也一样。
- **证据**：三次相互独立的 `pi -p` 会话，前后传递同一个状态文件，openai26 每次都返回 503 账号池：
  ```
  == session 1   stdout: hi from bai   pi exit=0   "failovers": 1 "failoversWithoutProgress": 0
  == session 2   stdout: hi from bai   pi exit=0   "failovers": 2 "failoversWithoutProgress": 1
  == session 3   stdout:（空）         pi exit=1   stderr: 503: {"message":"账号池暂无可用账号"}
  "customType":"x-failover","data":{"class":"E1","action":"handoff",...}
  ```
- **影响**：日常短任务（不建 run）大约在第三次主模型故障时就失去降级能力，而且之后**永久失效**，直到有人手动删除状态文件。
- **修复建议**：计数按 `sessionId` 维度存（`ctx.sessionManager` 能提供会话 id），在 session_start 或新的用户轮次时重置。`tool_result` 累计不要依赖 active run。`MAX_FAILOVERS_PER_RUN` 只对真正的 run 生效。

#### P0-4　分类规则和 pi 实际的错误文本格式不匹配：401/403/429/5xx 都判成 none　【已复现】

- **位置**：`classify.ts:27-37`（E1 用 `/HTTP\s*401\b/`、`/\bstatus\s*401\b/i`）、`classify.ts:59-61`（只有传入 `status` 时才用状态码，但 `x-failover.ts:115-119` 从不传 `status`）
- **现象**：pi 1.3.0 对 openai-completions 的 HTTP 错误，生成的 `errorMessage` 形如 `401: {"message":"Invalid API key",...}`，状态码后面跟冒号，前面没有 “HTTP”。
- **证据（真实 pi）**：
  ```
  $ ./run.sh e401 '[{"status":401,"body":{"error":{"message":"Invalid API key",...}}}]' '[{"text":"hi from bai"}]'
  pi exit=1
  stderr: 401: {"message":"Invalid API key","type":"invalid_request_error"}
  state:  "breakers": {}        ← 没有熔断，也没有切换
  ```
  **证据（纯逻辑，用真实格式）**：
  ```
  "401: {\"message\":\"Invalid API key\"}" => none
  "403: {\"message\":\"forbidden\"}" => none
  "429: {\"message\":\"Rate limit reached\"}" => none
  "500: {\"message\":\"Internal Server Error\"}" => none
  "502 Bad Gateway" => none
  "503 account_pool_forbidden" => none        ← DECISIONS.md 记录过的真实历史错误
  ```
- **影响**：凭证过期、限流、网关 5xx，以及 DECISIONS.md 里记录过的 `account_pool_forbidden`，都不会触发降级。run-guard 又会忽略 error 结局（`guard-core.ts:30`），所以长任务会直接停下，也不写 handoff。
- **修复建议**：从 errorMessage 里用 `^(\d{3})\b` 解析出状态码，作为 `status` 传入。401/403 判 E1；429 判 E1 或 E2（按 Retry-After 区分）；500/502/503/504 判 E2 或 E3。补上 `account_pool_forbidden`、`rate limit`、`overloaded` 等关键词。对分类为 none 但 `stopReason === "error"` 的情况设一个兜底，例如按 E3 处理。分类测试要用 pi 真实格式的样例，现有 `HTTP 524` 这类手写样例不够。

---

### P1：应该修

#### P1-1　xr 没有锁，也不做原子写：重复派发和丢失更新　【已复现】

- **位置**：`xr:79-83`（`write_tsv` 直接 `write_text`）、`xr:381-405`（`cmd_next` 读、改、写）、`xr:412-445`（`cmd_verify` 在跑验证命令前读出 rows，跑完再整表写回）
- **现象**：pi 会并行执行同一条消息里的多个工具调用，Brief 也要求子代理自己调用 `xr gate`，所以并发调用 xr 是正常使用场景。
- **证据 1（重复派发）**：5 个 research 单元，8 个并发 `xr next`：
  ```
  ok next R1 doing
  ok next R1 doing      ← R1 派了两次
  ok next R2 doing
  ok next R3 doing
  ok next R4 doing
  ok next R3 doing      ← R3 派了两次
  ok next R5 doing
  ```
- **证据 2（丢失更新）**：`xr verify A`（验证命令是 `sleep 2`）运行期间执行 `xr next`：
  ```
  ok next A doing
  ok next B doing
  ok verify A VERIFIED e3b0c44298fc1c14
  --- 最终 units.tsv
  A  verifying
  B  todo        ← 刚派出去的 B 被 verify 用旧数据覆盖回 todo
  ```
- **影响**：两个 worker 改同一个文件集，或者某个 worker 的单元在账本上“消失”，违反“doing 单元的文件集互不相交”这条质量检查。
- **修复建议**：所有写操作放在 `fcntl.flock(run/.lock)` 里，覆盖完整的读、改、写过程。写文件改成“临时文件 + `os.replace`”。`cmd_verify` 不要在执行外部命令期间持有旧的 rows：跑完验证后重新加锁、重新读、再写。

#### P1-2　verify 缓存不认验证命令，scope 不存在也能 VERIFIED，done 不检查状态　【已复现】

- **位置**：`xr:417-422`（缓存键只有 `unit+tree_hash`）、`xr:177-195`（scope 下没有文件时返回空串的哈希）、`xr:453-463`（`cmd_done` 不检查是否是 doing/verifying）、`xr:349`（plan add 替换时保留旧 ledger）
- **证据**：
  ```
  $ xr plan add A a --files a.txt --verify true ; xr verify A
  ok verify A VERIFIED a3dd2996f0abc24e
  $ xr plan add A a --files a.txt --verify false
  ok plan A updated units=1 mode=main
  $ xr verify A
  ok verify A VERIFIED a3dd2996f0abc24e cached     ← 新命令 false 根本没跑
  $ xr done A
  ok done A
  ```
  ```
  $ xr plan add D1 d --files nonexist.txt --verify true ; xr verify D1 ; xr done D1
  ok verify D1 VERIFIED e3b0c44298fc1c14            ← sha256("") 的前 16 位
  ok done D1                                         ← 没经过 next/doing
  ```
- **影响**：“拒绝没有 VERIFIED 的 done”是 v3 的完成门，这个门可以被轻易绕过，模型重规划时也可能无意中绕过。验证命令通常还依赖 scope 之外的测试文件，这些文件变了，缓存照样命中。
- **修复建议**：缓存键加上 `sha(verify_cmd)`，并允许声明额外的输入路径，或者干脆默认不缓存。scope 为空时直接拒绝。`done` 只接受 `verifying` 或 `doing` 状态。`plan add` 替换单元时让旧 ledger 失效。

#### P1-3　E2 同模型重试计数永不清零，第二次 E2 会直接切换　【已复现】

- **位置**：`switch.ts:99-101`、`switch.ts:118-133`（`memoryAfter` 只在 switch 时把 `sameModelRetries` 归零）
- **证据（真实 pi）**：openai26 先返回 busy，再返回成功：
  ```
  openai26 req#1 ... "The service is busy"
  openai26 req#2 ... last="[x-failover] E2 同模型再试 1 次"  → 成功
  state: "session": { "sameModelRetries": 1, ... }      ← 重试成功后仍然是 1，而且跨会话保留
  ```
  **纯逻辑**：
  ```
  t=0 第1次 E2: retry-same
  t=+3h 新的一次 E2: switch
  ```
- **影响**：C4 的设计是“同模型重试 1 次”，实际变成了“这个 run（或全局 session）一辈子只重试 1 次”。之后每次偶发的 E2 都会立刻切到 bai。fallback 上的 E3/E5 重试（`switch.ts:103`）也有同样的问题。
- **修复建议**：一个成功的 assistant 回合（stopReason 是 stop 或 toolUse）之后把 `sameModelRetries` 清零，或者按“同一次失败链”来计数。

#### P1-4　failback 状态机有三个死角：E2/E4 切走后永不切回、锁定是全局永久的、开启探活后永不切回　【已复现】

- **位置**：`breaker.ts:74-76`（`cooldownElapsed` 要求 `state.open`）、`x-failover.ts:120`（E4 不进熔断）、`breaker.ts:38-53`（`open()` 里 `lockedToFallback` 只会置 true）、`failback.ts:29-31`、`x-failover.ts:86`、`x-failover.ts:175-181`（`applyProbe` 没有任何调用方）
- **证据（纯逻辑）**：
  ```
  ## C. E2 触发的切换之后永不 failback
  breaker.open = false e2Times = 2
  2 小时后单元边界: { action: 'stay', reason: '冷却未结束' }
  ## D. E4 触发的切换之后永不 failback
  klass = E4 action = switch breaker.open = false
  2 小时后: 冷却未结束
  ## E. lockedToFallback 全局永久
  locked = true
  +1 天, 新 run: 切回后 15 分钟内再次熔断，本 run 留在兜底模型
  +30 天, 新 run: 切回后 15 分钟内再次熔断，本 run 留在兜底模型
  ```
- **现象补充**：
  - E2 第 2 次就切换了，但熔断要 10 分钟内 3 次才打开。所以“E2 导致的切换”在熔断器眼里根本不存在，冷却永远“未结束”。
  - `lockedToFallback` 存在全局的 breaker 上，注释写的是“本 run 留在兜底模型”，实际效果是永远留在兜底模型。
  - `X_FAILOVER_PROBE=1` 时要求 `consecutiveProbeOk >= 2`，但没有任何代码会调用 `applyProbe`，所以开启探活后永远不切回。
- **影响**：用户会长期停留在 bai 上，而且很难察觉。
- **修复建议**：只要发生 switch，就把主模型的 breaker 置为 open（带冷却）。`lockedToFallback` 按 runId 存，或者带上过期时间。探活没实现之前，删掉这个环境变量分支。

#### P1-5　压缩时的“对话要点”补充摘要发送的是空消息　【已复现】

- **位置**：`x-run-guard.ts:173-177`（`ctx.modelRegistry.complete(model, { messages: [] }, ...)`）、`x-run-guard.ts:147-160`
- **证据**：用一个最小扩展，以同样的参数调用 `complete`：
  ```
  bai req#1 model=deepseek-v4.1-flash msgs=0 ...          ← 请求体里没有任何消息
  {"stopReason":"stop","content":[{"type":"text","text":"SUMMARY-TEXT"}]}
  ```
- **影响**：真实 provider 收到这个请求，要么返回 4xx（这时补充摘要静默变成 null），要么返回和对话毫无关系的文本。不管哪种，都会以“## 对话要点”的名义写进压缩摘要。加上 `session_before_compact` 只要存在 active run，就会接管**所有**压缩（包括 pi 按阈值自动触发的压缩），对话里用户的临时指示会全部丢失，只剩下不超过 2KB 的胶囊。
- **修复建议**：把 `event.preparation` 里待摘要的消息（或 `branchEntries`）连同一条系统指令传给摘要模型。或者在补充摘要可用之前去掉这个功能，同时在文档里说明“压缩只保留胶囊”。

#### P1-6　只要 repo 里有 ACTIVE run，每个正常结束的回合都会被强制续跑　【已复现】

- **位置**：`x-run-guard.ts:90-145`、`guard-core.ts:25-43`
- **现象**：只要 `.work-docs/runs/ACTIVE` 存在，而且还有没完成的单元，模型向用户提问（Frame 阶段的 grilling 就要求这样做）、闲聊、回答无关问题，都会被注入“不要向用户要‘继续’”的消息，最多连续 3 次。`ACTIVE` 没有任何 verb 能清除，run 完成以后它依然存在。
- **证据**：
  ```
  # SETUP：xr init；plan U1
  $ ./run.sh guard '[{"text":"我需要你确认一下目标再继续，可以吗？"}]' ... "帮我做个任务"
  openai26 req#1 ... last="帮我做个任务"
  openai26 req#2 ... last="[x-run-guard] 继续 run ...不要向用户要“继续”。"
  openai26 req#3 ... 同上
  openai26 req#4 ... 同上
  events: resume ×3 → handoff "连续 3 次续跑后 units 和 ledger 都没有变化"
  ```
- **仅代码推断（风险）**：pi-subagents 拉起的子 pi 进程默认也会加载 `~/.pi/agent/extensions`。只读子代理如果在主 repo 的 cwd 下运行，同样会被 run-guard 强制续跑，被要求“从 doing 单元接着做”，也会与主会话争用 `x-failover.json`（见 P1-10）。
- **影响**：浪费 token；破坏 Frame 阶段与用户的必要交互；并发时子代理可能越权做编排工作。
- **修复建议**：只有在本会话发起或恢复过这个 run 时才续跑。可以在 session 里 `appendEntry` 一个 run 绑定标记，在 `/x-rail resume` 时写入。检测到最后一条 assistant 消息是向用户提问时跳过续跑。子进程可以用环境变量（如 `X_RAIL_SUBAGENT=1`）来禁用 run-guard。增加 `xr close` 来清除 ACTIVE。

#### P1-7　“熔断时子代理并发减半”实际不生效　【已复现】

- **位置**：`xr:156-170`（`breaker_open()` 只读 `X_FAILOVER_STATE` 环境变量）、`extensions/subagent.ts`（`concurrencyLimits`、`dispatchModel`、`reviewerFamily` 只被测试引用，运行时没有任何地方调用）
- **证据**：HOME 默认位置的状态文件里主模型 breaker 是 open：
  ```
  == 熔断已打开（默认状态文件），未设 X_FAILOVER_STATE
  ok next W1 doing
  ok next W2 doing           ← 仍然允许 2 个写入者
  == 设置 X_FAILOVER_STATE 后
  ok next W1 doing
  ok next none               ← 这时才降到 1
  ```
- **影响**：Execute 阶段卡第 4 步写着“熔断打开时合计 2、写入 1，`xr next` 会拒绝……超额”，实际做不到。另外，bai 自己的 breaker 一旦打开就永远不会关闭，因为 `noteFailback` 只处理主模型。如果设置了环境变量，又会导致永久减半。
- **修复建议**：xr 回落到 `~/.pi/agent/state/x-failover.json`，与 `store.ts` 的 `statePath` 保持一致，而且只看主模型的 breaker。删掉或者真正接入 subagent.ts，避免两处各写一份常量（constants.ts 第 1 行的注释已经承认需要“同时改 xr”）。

#### P1-8　gate 不能关闭，被 gate 挡住的单元没有合法出路　【已复现】

- **位置**：`xr:523-548`（只有新增 gate，没有 resolve 或 close 的 verb）、`xr:349-350`（blocked 单元不能 `plan add` 替换）、`run-files.ts:60-61`（`gateOpen = /status: open/.test(gates)`）
- **证据**：
  ```
  $ xr gate "要不要用 X？" --default "用 X" --unit G1
  ok gate G1
  $ xr plan add G1 g --deps none --files g.txt --verify true
  xr: 单元 G1 正在 blocked，不能改。正确命令：xr status
  $ xr gate close G1
  xr: 参数不对。……（没有这个 verb）
  ```
- **影响**：Frame 阶段卡规定“执行期不再提问；新问题用 xr gate”，Land 阶段卡又说“Land 前无答复即按默认执行”，但没有命令能执行默认做法或解除阻塞。唯一的“出路”是误用 `xr fail G1 --kind net` 把单元打回 todo，或者手改 TSV，而手改 TSV 是文档禁止的。
- **修复建议**：增加 `xr gate resolve G<n> --answer ...|--default`，把 gates.md 里的状态改为 resolved，并把关联单元恢复为 todo。

#### P1-9　在 macOS 自带的 Python 3.9 上，`xr next` 会崩溃　【已复现（用 CPython 3.9.25）】

- **位置**：`scripts/frontier.py:19`（`zip(a, b, strict=False)`，要 Python 3.10 以上），v3 新增的代码
- **证据**：
  ```
  $ python3.9 xr next      # 已有一个 doing 单元
    File ".../frontier.py", line 19, in overlap
      for first, second in zip(a, b, strict=False):
  TypeError: zip() takes no keyword arguments
  ```
  在 3.9 下运行 `test-xr.py`，`test_overlap_verify_done_and_fail` 失败。
- **影响**：xr 的 shebang 是 `/usr/bin/env python3`。机主的 Mac 如果用的是 Xcode CLT 的 `/usr/bin/python3`（3.9.x），只要有 doing 单元，`xr next` 就不可用。是否会触发取决于机主 PATH 里排在前面的是哪个 python3，这一点需要机主确认。
- **修复建议**：去掉 `strict=False`（这里本来就是默认行为）。在 CI 或 check 脚本里加一个 3.9 兼容性检查，或者在 xr 开头明确检查 Python 版本并给出提示。

#### P1-10　`x-failover.json` 在多进程并发写时会丢数据，还会抛异常　【已复现】

- **位置**：`store.ts:33-38`（固定的临时文件名 `${file}.tmp` 加 `renameSync`，没有锁）、`x-failover.ts:55-64`（每次 tool_result 都读、改、写）
- **证据**：3 个进程同时做“load → +1 → save”各 2000 次：
  ```
  C saveState 抛错次数 963
  B saveState 抛错次数 1004
  A saveState 抛错次数 892
  B toolCalls 期望 2000，实际 1
  A toolCalls 期望 2000，实际 186
  （C 的记录整条丢失）
  ```
- **影响**：多个 pi 会话或子代理同时运行时，熔断状态、失败计数和工具进展计数会互相覆盖。抛出的 ENOENT 会让当次 before_settle 处理器直接中断，于是这一次既不切换也不续跑。
- **修复建议**：临时文件名加上 pid 和随机后缀。读、改、写放在文件锁里（例如 `proper-lockfile`，或用 `fs.openSync(lock, "wx")` 自旋）。按会话和 run 拆分文件，可以减少争用。

#### P1-11　安装：旧布局的残留文件会让 pi 无法启动；v3 安装测试失败；check-repo 没有覆盖 v3　【已复现】

- **位置**：`install.sh:25-39,87-109`；`scripts/test-install-v3.sh:15-16`；`scripts/check-repo.sh`（没有调用任何 v3 测试）
- **现象**：`6b3c1ca` 版本的安装器（test-install-v3 至今还在断言这个位置）把 13 个 .ts 直接装进 `~/.pi/agent/extensions/`。新安装器改到 `extensions/x-rail/`，但不清理旧文件。pi 会把顶层的辅助模块当成扩展加载，然后报错退出。
- **证据**：模拟旧布局后，再运行新安装器和 pi：
  ```
  清单未变化 .../extensions/x-rail/package.json
  extensions/: breaker.ts classify.ts ... x-failover.ts x-rail x-run-guard.ts
  pi exit=1
  Error: Failed to load extension ".../extensions/breaker.ts": Extension does not export a valid factory function
  ...（11 行同类错误）
  ```
  ```
  $ bash scripts/test-install-v3.sh
  + [[ -f /tmp/tmp.W9LXJ9hXFC/.pi/agent/extensions/x-failover.ts ]]    → exit 1
  ```
- **影响**：如果机主已经在 Mac 上用 `6b3c1ca` 的安装器装过一次，升级后 pi 会直接起不来。就算 pi 能启动，顶层的 x-failover.ts 和 x-rail/x-failover.ts 也会各注册一遍，导致重复切换、重复续跑。v3 的测试不在 check-repo 里，这个回归就没有被发现。
- **修复建议**：安装器在写入新布局前，检测并备份顶层的同名文件（`EXT_FILES` 列表里的那些）。修正 test-install-v3 的断言，并加一个“旧布局升级”的用例。把 test-xr、test-failover、typecheck、test-install-v3 都纳入 check-repo（或者至少纳入一个 `check-v3.sh`）。

---

### P2：建议

#### P2-1　scope 里的软链可以读到仓库外的文件，并让 xr 崩溃　【已复现】
- **位置**：`xr:181-193`（`rglob` 之后 `resolve()`，再 `relative_to(repo)`）
- **证据**：`ln -s /etc/hostname src/link; xr plan add S1 s --files src --verify true; xr verify S1`，输出 `ValueError: '/etc/hostname' is not in the subpath of '/tmp/xr4'`，exit=1，并打印 Python traceback。
- **修复建议**：跳过软链，或者在 resolve 之后检查路径仍在 repo 内，出错时给出 xr 风格的错误提示。

#### P2-2　字段中含 U+2028 等字符时，写入成功，但之后整张表都读不出来　【已复现】
- **位置**：`xr:53-56`（`cell` 只拦 `\t \n \r`）与 `xr:62`（`read_text().splitlines()` 还会在 `\x0b \x0c \x1c-\x1e \x85 \u2028 \u2029` 处断行）
- **证据**：`xr plan add T1 "$(printf 'a\u2028b')" ...` 输出 `ok plan T1 added`；此后 `xr status` 和 `xr next` 都输出 `xr: units.tsv 有一行字段数不对`，exit=2，这个 run 无法再用 xr 恢复。
- **修复建议**：读取时改用 `split("\n")`，或者在 `cell` 里拒绝 `str.splitlines` 会识别的所有分隔符。

#### P2-3　`xr fail` 不检查单元状态，可以把 done 单元打回 todo　【已复现】
- **位置**：`xr:477-500`
- **证据**：`xr fail D1 --kind net` 作用于已 done 的单元，输出 `ok fail D1 todo attempts=1`。
- **修复建议**：只允许对 doing 或 verifying 状态的单元执行 fail。

#### P2-4　verify 超时会丢掉已有输出，并留下孤儿进程　【已复现】
- **位置**：`xr:423-432`
- **证据**：verify 命令为 `echo start; sleep 30 & sleep 30; echo never`，加 `--timeout 2`：耗时 2.056s，结果 `FAILED`，证据日志为空（`start` 没有保存下来），而且有两个 `sleep 30` 进程残留。
- **现象说明**：在 POSIX 上，`TimeoutExpired.stdout` 是 bytes，代码只接受 str，所以输出被丢弃；`shell=True` 只能杀掉 sh 本身，杀不到它的子进程。
- **修复建议**：用 `start_new_session=True` 启动，超时时 `os.killpg` 杀整个进程组。bytes 输出要解码后写入日志，并在 ledger 里标注 timeout。

#### P2-5　`install.sh --no-backup` 行为错误　【已复现】
- **位置**：`install.sh:43-48,80-83`
- **证据**：
  - 目标已经是目录时，输出“已链接”，但软链实际建在了旧目录里面（`skills/x-rail/x-rail -> ...`），旧的 SKILL.md 原样保留；
  - 目标是普通文件时，`ln: failed to create symbolic link ... File exists`，exit=1，安装只完成了一半。
- **修复建议**：`--no-backup` 时先 `rm -rf` 掉旧目标（要求用户确认），或者干脆移除这个选项。

#### P2-6　两套安装器互相冲突，v3 安装器没有文档　【已复现】
- **证据**：先跑 v3 的 install.sh，再跑 `scripts/install.sh`：`install: refusing to replace symlink .../skills/x-rail in copy mode`，exit=1。反过来先跑 scripts/install.sh，v3 会把 4 个技能的拷贝备份后改成软链，其余 28 个配套技能仍然是拷贝，版本会混杂。README、docs 和 DECISIONS 里都没有提到 `skills/x-rail/install.sh`。
- **修复建议**：明确只保留一个安装入口，或者让 scripts/install.sh 识别 v3 的软链。README 写清楚升级步骤。

#### P2-7　boundary 处理器返回 entries 时，会覆盖前面扩展追加的条目　【仅代码推断】
- **位置**：`x-failover.ts:147-150,167-170`、`x-run-guard.ts:141-144`；pi `runner.js:776`（`entries = handlerResult.entries`，是替换不是合并）
- **影响**：当两个扩展在同一次 settle 中都返回 entries 时，先执行的那个扩展的消息会丢失。目前两者的触发条件大致互斥（error 结局对 completed 结局），但修 P0-1、P0-2 时很容易让它们重叠。
- **修复建议**：一律返回 `entries: [...event.entries, 新条目]`。

#### P2-8　Brief 和 Execute 卡要求的 worktree 分支名，会被 x-worktree 拒绝　【已复现】
- **位置**：`stages/execute.md` 第 3 步和 `references/brief-template.md`（分支 `xr/run/unit`）对 `x-worktree/scripts/create_worktree.sh:34`（名字里不能含 `/`）
- **证据**：`create_worktree.sh xr/20261017-demo/U1 --main main` 输出 `name must not contain '/', '..' or a leading dot`，exit=2。
- **修复建议**：统一分支名，例如 `xr-<run>-<unit>`，或者让脚本把分支名和目录名分开处理。

#### P2-9　阶段卡要求模型“调用”的技能，被设置成只能由用户调用　【仅代码推断（基于 pi 文档）】
- **位置**：`x-handoff/SKILL.md:4` 和 `x-self-check/SKILL.md:4` 都设了 `disable-model-invocation: true`，而 `stages/land.md` 第 4、5 步写的是“可调用 x-handoff”“Reflect：调用 x-self-check”。另外，x-handoff 只写 `.work-docs/tasks/TASK_ID/handoff.md`，而 run-guard 写的是 `.work-docs/runs/<id>/handoff.md`，两者路径也不一致。
- **补充**：阶段卡里多处写“调用 Skill 工具 grilling/tdd/code-review”，但 pi 1.3.0 本体没有名为 Skill 的工具（`dist/core/tools/` 下只有 bash/edit/find/grep/ls/read/write/powershell）。除非机主另外装了提供这个工具的扩展，否则应该改成“读取对应的 SKILL.md”。
- **修复建议**：Land 卡改成“提示用户运行 `/skill:x-handoff`”，或者去掉 disable 标志，并把 handoff 路径统一到 runs/。

#### P2-10　文档里写了、代码却没读的配置　【仅代码推断（grep 证据）】
- `config/examples/1.5-smart-compact.jsonc:9-18` 定义了 `"x-failover": { primary, fallback, cooldownMin, maxCooldownMin, failback, failbackMaxContextTokens, maxFailoversPerRun, streamWatchdogSec }`。扩展里没有任何代码读 settings，所有值都硬编码在 `constants.ts` 里。用户改了这里，什么都不会变。
- RUN.md 骨架里的 `failback: auto`（`xr:254`）没有被读取，`x-failover.ts:81` 写死了 `policy: "auto"`。`model: unknown` 没有任何命令会更新，所以 ledger 和 decisions 里的 model 列永远是 `unknown`，Land 阶段卡要求写的“哪个模型做的”无从得出。
- Budgets 的“墙钟到 70% 就停止开新单元”：xr 和扩展都不读墙钟。Review 卡要求的“fixed point 是 run 起点的 SHA”：`xr init` 没有记录起点 SHA。
- **修复建议**：要么实现读取，要么从文档和示例里删掉，免得用户以为这些配置在生效。

#### P2-11　文档之间、文档与代码之间的规则不一致　【仅代码推断】
- `stages/execute.md` 第 8 步写“验证连续失败 2 次就 abandoned”；`references/failure-modes.md` 写“logic / verify：直接 abandoned”；xr 的实现是 `fail --kind verify` 一次就 abandoned，而 `xr verify` 得到 FAILED 时不改变任何状态、也不计次数。
- DECISIONS C4 写“E2 十分钟三次才打开”，但 `decideSwitch` 在第 2 次 E2 就已经切换（见 P1-4）。
- commit `63e67c0` 的说明是“……或写出 handoff”，但 x-failover 的 handoff 分支（`x-failover.ts:139-142`）只弹通知、记一条事件，不写 handoff.md。run-guard 又忽略 error 结局，所以降级失败时不会留下 handoff 文件。

#### P2-12　测试质量：有的测试不可能失败，关键路径没有测试　【代码阅读】
- `scripts/test-mock26.mjs:9-35` 只验证 mock 服务把自己的脚本原样返回（`assert.equal(response.status, step.status)`），没有调用分类器，也没有调用 pi，属于自证循环。
- `failover.test.ts:126` 的 `assert.ok(HYSTERESIS_MS > 0)` 没有意义。整个文件只测纯函数，没有覆盖任何事件处理器、abort 或 compact 的副作用，也没有覆盖状态文件的持久化语义。P0-1 到 P0-3 都出在这些没测到的地方。
- `test-xr.py:132-141` 通过注入 `X_FAILOVER_STATE` 来测试“熔断减半”，恰好绕开了 P1-7 的默认路径缺陷。xr 没有并发测试，没有 gate 解除测试，也没有“改了验证命令必须重跑”的测试。
- 分类测试用的是手写的 `HTTP 401`、`HTTP 524`，没有用 pi 真实生成的 errorMessage 格式（见 P0-4）。
- **修复建议**：把本报告的 `e2e/run.sh` 和 `mock.mjs` 改造成正式的 `scripts/test-e2e-pi.sh`（离线运行，不花钱）。

#### P2-13　每个新会话都会先撞一次已经熔断的主模型，冷却时间随之翻倍　【已复现】
- **位置**：x-failover 没有在 `session_start`、`before_agent_start` 或 `model_select` 时检查熔断状态；`breaker.ts:38-40`（已经 open 时再次 open，冷却翻倍）
- **证据**：三次独立会话之后 `openCount/cooldownMs` 依次为 `1 900000`、`2 1800000`、`3 3600000`，每个会话都先向 openai26 发了一次请求。
- **修复建议**：会话开始时如果主模型的 breaker 处于 open 且冷却未结束，直接 `setModel(bai)`。已经 open 的情况下再观察到错误，不要重复翻倍。

#### P2-14　杂项
- `events.jsonl` 里的时间戳格式混用：xr 写 `+08:00`，扩展写 UTC `Z`（已复现，见 P0-2 证据中的 events），按时间排序和人工阅读都容易出错。
- failback 之后 thinking 仍停在切换时设的 `high`（`x-failover.ts:164`），没有恢复到主模型原来的级别（仅代码推断）。
- `resumeHint` 不检查 doneMet，再加上 ACTIVE 永不清除，已经完成的 run 每次开会话都会提示“有未完成的 run”（仅代码推断）。
- `.work-docs` 被 gitignore，worker 在自己的 worktree 里按 Brief 执行 `xr gate`，会得到“没有 active run”，因为 Brief 没有让它带 `--repo <主仓库>`。`notes/单元-report.md` 的路径对 worker 也不可达（仅代码推断）。
- `xr import`（`xr:668-686`）给导入的单元写死 `verify_cmd = "true"`，等于给 done 门开了后门；出现依赖环时静默不保存，却仍然输出 `ok import ... units=N`（仅代码推断）。
- E3 的 `/\bterminated\b/`、E4 的 `/\b422\b/` 匹配范围偏宽，例如 `socket terminated by peer while parsing line 422` 会被判成 E3（已复现，c2.ts）。目前只在出错回合生效，影响有限。
- `self_check.py:27` 在 SKILL.md 没有 frontmatter 时会抛 IndexError，而不是给出明确的失败提示（仅代码推断）。

---

## 5. 做得好的地方

- **纯函数分层清楚**：classify、breaker、switch、failback、guard-core 都是纯函数，时间作为参数注入，很容易测试。本报告的逻辑复现可以直接导入这些模块。
- **正常回答里出现错误字样不会误判**：`d6fc6a1` 只在 `stopReason === "error"` 的回合读取正文，避免了讨论“HTTP 401”时误触发降级，回归测试也写了。
- **工具执行期间暂停看门狗**（`3c8488a`），考虑到了同步子代理长时间不出 token 的情况。
- **主降级路径端到端可用**：以文本可识别的 E1 为例，`503 账号池暂无可用账号` 能正确熔断、切到 bai、设置 thinking high、注入续跑提示，bai 也收到了请求，会话里留下了 `custom x-failover` 审计条目。
- **xr 的报错一致**：都带“正确命令”提示；对 slug、id、scope（绝对路径和 `..`）、依赖存在性、依赖环都有校验；capsule 有 2KB 上限并按字节截断；`xr import` 会核对旧任务文件的哈希，保证不改动旧文件。
- **安装器考虑周到**：兼容 bash 3.2（去掉了关联数组，全仓库 .sh 扫描没有发现 bash 4 特性），用 package.json 的 `pi.extensions` 清单只声明两个入口，幂等，默认备份，并提供 dry-run。
- **阶段卡精简**：self_check 限制了入口和阶段卡的体积（入口 4545 字节），DECISIONS.md 对 C1–C7 都写明了选择、理由和重新评估的条件，方便以后核对。

---

## 6. 建议修复顺序

1. **P0-4 分类器**：解析状态码，补充真实错误串。改动最小，收益最大，先让降级在 401/429/5xx 下能触发。
2. **P0-1 + P0-2 运行时接线**：看门狗改成不依赖 before_settle；before_settle 里改用 compaction draft，或者在 settle 之后压缩再 triggerTurn。顺手处理 P2-7（entries 追加）。这两项要一起设计。
3. **P0-3 + P1-3 + P1-4 + P2-13 状态与计数**：按会话和 run 分开存；成功回合后清零重试计数；切换时让熔断打开；锁定带过期时间；去掉探活分支；新会话预先检查熔断。
4. **P1-10 + P1-1 并发安全**：x-failover.json 和 xr 的 TSV 都加锁并原子写。
5. **P1-2 + P2-3 完成门**：缓存键包含验证命令；拒绝空 scope；检查状态迁移是否合法。
6. **P1-8 gate resolve、P1-6 run-guard 绑定会话、P1-7 熔断并发读默认路径、P1-5 补充摘要**。
7. **P1-9 Python 3.9 兼容、P1-11 安装器迁移与测试**：把 v3 测试接入 check-repo。
8. **补上测试**：把 e2e mock 套件正式化，覆盖本报告每条“已复现”问题（P2-12）。
9. 其余 P2（文档对齐、--no-backup、两套安装器、杂项）。

---

## 附：复现材料位置

- 端到端复现台：`/workspace/v3-cr/e2e/run.sh`、`/workspace/v3-cr/e2e/mock.mjs`；各场景输出在 `/workspace/v3-cr/e2e/<case>/`（wd、compactswitch、boundary、boundary2、guard、e401、e503pool、e2、sess1-3、dup）
- 扩展隔离验证：`/workspace/v3-cr/e2e/iso/`；`complete()` 空消息探针：`/workspace/v3-cr/e2e/probe-complete.ts`
- 纯逻辑复现：`/workspace/v3-cr/repro/logic.ts`、`c2.ts`、`store-race.ts`
- 被测副本：`/workspace/v3-cr/run`（原样）、`/workspace/v3-cr/run-wd`（只把 `WATCHDOG_MS` 改成 8000，用于 P0-1）
- pi 1.3.0 源码参照：`/workspace/v3-cr/pi/node_modules/@earendil-works/pi-coding-agent/dist/core/`
