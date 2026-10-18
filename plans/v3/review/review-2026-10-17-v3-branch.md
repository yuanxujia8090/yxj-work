# x-rail v3 分支代码审查报告

- 日期：2026-10-17
- 审查对象：worktree `.worktrees/v3`，分支 `v3`（HEAD `3c8488a`），基线 `b158f20`（32 个提交，196 文件）
- 审查方式：只读。未修改任何被审文件；未提交、未推送、未安装、未删除。
- 取证方式：本体实测 + 3 个并行只读审查子代理（Python 脚本 / TS 扩展 / 文档与证据一致性）。每条标注“已复核”（我亲自跑过）或“子代理取证”（未复核）。

## 0. 等级定义

| 等级 | 含义 |
|---|---|
| **必修** | 会导致完成态造假、任务中断、状态不可恢复或并发写冲突；合并到 main 之前应修。 |
| **建议修** | 不会立刻造成损失，但会持续消耗信任/维护成本，或在特定条件下变成必修。 |
| **备注** | 事实记录与取舍说明，不需要立刻动作。 |

## 1. 结论摘要

**不建议现在合并 / 上线。** 理由：v3 的入口压缩目标达成得很好（SKILL.md 25,012 → 4,545 字节），`task.py` 一侧的完成门做得很严；但新引入的 `xr`/扩展这一层质量明显更弱——无文件锁、非原子写、完成态可被旧缓存冒充、故障分类会把正常回答判成故障。已有 10 条“必修”级问题，其中 7 条我亲自复现。

**最该先看三条**

1. **正常回答会被当成模型故障。** 扩展把“最后一条助手消息的正文”当错误文本分类；正文里出现 `HTTP 401`、`Connection error`、`bad request` 这类字样（讨论错误处理代码时极常见）就会判 E1 → 切模型 + 熔断 15 分钟。已复现。
2. **没有 active run 的会话，第 3 次失败后永久停。** run 记忆写死在 `"session"` 这个 key 上，永不重置、永不清理。已复现；本机 `~/.pi/agent/state/x-failover.json` 里已经存在 `runs.session`。
3. **`xr verify` 的缓存不看验证命令。** 把单元的 `--verify` 从 `true` 改成 `false` 后，`xr verify` 仍返回 `cached VERIFIED`，`xr done` 照样通过。已复现。

**验收层面的核心失分**：v3-goal 第九节要求“不存在通过拆分文件而增加总复杂度的假优化”。实测 `skills/x-rail/**` 的 Markdown 总量 109,854 → 136,461 字节（+24%），同时库里现在**并行存在两套任务模型**（旧的 task.py 证据模式 + 新的 xr run 模式），入口没有写清二者分工。

---

## 2. 必修问题

### M1 正常回答被判定为 provider 故障（误切模型 + 误熔断）

- 位置：`skills/x-rail/extensions/classify.ts:103-111`、`x-failover.ts:105-134`
- 现象：`assistantErrorText` 把助手消息的 `content` 正文拼进待分类文本；`agent_before_settle` 里对**所有** outcome 都调用 `classifyError`，不过滤正常完成。
- 证据（已复核）：构造一条正常完成的助手消息，正文写“在 fetch 里遇到 HTTP 401 时要刷新 token，Connection error 也要重试”，分类结果 `{"klass":"E1","matched":"HTTP 401","immediateFailover":true}`。
- 影响：正常回答触发立即切到 bai、primary 熔断 15 分钟起并逐次翻倍；用户默认模型就是 bai 时，在 bai 上再遇到可切换错误会直接 handoff 停掉任务。
- 方案：分类只用 `errorMessage` / 非 `completed` 的 outcome，正文不进 `text`；或在 `agent_before_settle` 里按 `event.outcome` 门控。
- 风险：收紧后 E2/E3 的真实错误串仍来自 `errorMessage`，但要回放验证不误伤；`stopReason` 语义需按宿主实际值确认。

### M2 无 active run 时 run 记忆写死 `"session"`，永不重置 → 永久 handoff

- 位置：`x-failover.ts:70`（`located?.id ?? "session"`）、`store.ts:9-19`
- 现象：没有 active run 的会话共用同一个 `runs["session"]` 桶；`state.runs` 无删除、无重置路径。
- 证据（已复核）：`decideSwitch` 在 bai 上连续 E3 的模拟输出——第 1 次 `retry-same`，第 2 次起永久 `handoff`（`memoryAfter` 对 handoff 不改变记忆）。本机 state 文件确认存在 `runs.session`、且 `bai/deepseek-v4.1-flash` 熔断已 open。
- 影响：普通对话在 3 次可切换错误后永久不再换模型，跨会话、跨重启保持；`failovers` 也累计到 8 次上限。
- 方案：`session_start` 时清空该桶，或改用真实 session id，或没有 active run 时不落盘。
- 风险：按 session id 分桶会让 state 文件更快膨胀，需要清理策略。

### M3 `xr verify` 缓存键不含验证命令 → 完成态被旧缓存冒充

- 位置：`skills/x-rail/scripts/xr:419-421`（缓存命中判定）、`448-451`（`verified_now`）
- 现象：缓存键只含 `(unit, tree_hash, verdict=VERIFIED)`，不含 `verify_cmd`。
- 证据（已复核）：

  ```text
  ok verify u1 VERIFIED 4d61247d70ceadd5
  ok plan u1 updated units=1 mode=main      # verify_cmd 改成 "false"
  ok verify u1 VERIFIED 4d61247d70ceadd5 cached
  ok done u1
  ```
  ledger 里留着 `cmd=true, exit_code=0`，而 units.tsv 当前 `verify_cmd=false`。
- 影响：验证判据被改动后，完成门放行未经执行的新判据 —— 正是 v3-goal 明确禁止的“检查器制造虚假完成状态”。
- 方案：缓存键加入 `verify_cmd`（或其哈希）；或 `plan add` 替换单元时清掉该 unit 的 VERIFIED 行。
- 风险：加键后旧 ledger 行需要兼容读；`xr import` 会带来 `verify_cmd=true` 的占位值，需明确语义。

### M4 `xr done` 无终态守卫，done 可被改写

- 位置：`xr:477-495`（fail）、`523-545`（gate）；`TERMINAL = {"done","abandoned"}` 定义于 `xr:29` 但全文件再无引用
- 证据（已复核）：

  ```text
  ok done a
  ok fail a --kind net   → units.tsv: a  state=todo  attempts=1
  ```
- 影响：已完成的单元可被一条命令抹回未完成并污染 attempts；`done` 语义不再是终态。
- 方案：`cmd_fail`/`cmd_gate`/`cmd_plan_add` 入口统一加 `if row["state"] in TERMINAL: die(...)`（把已定义未接线的 `TERMINAL` 接上）。
- 风险：需要给“确实要重开”的场景留一条显式路径（例如 `xr reopen`），否则用户只能手改 TSV。

### M5 gate 会把 doing 单元的独占文件占位释放 → 同文件两个 doing

- 位置：`xr:385`（并发判定只统计 `state == "doing"`）与 `xr:540-544`（gate 把单元改成 `blocked`）
- 证据（已复核）：

  ```text
  ok next a doing
  ok gate G1
  ok next b doing        # b 的 --files 与 a 相同（src/a.txt）
  units.tsv: a blocked src/a.txt ; b doing src/a.txt
  ```
- 影响：与 `stages/execute.md:8` “`xr next` 会拒绝重叠文件和超额”直接矛盾；可能导致两个 worker 并发写同一文件。
- 方案：占位集合改为 `doing ∪ verifying ∪ blocked(未完成)`，或 gate 时保留占位记录。
- 风险：改动占位语义会影响 `next` 的吞吐，需要同步更新阶段卡承诺。

### M6 gate 只有打开、没有关闭路径 → 调度永久卡死

- 位置：`xr:523-545`；`extensions/run-files.ts:59-61` 的 `allBlockedByGate`
- 现象：`gates.md` 只被追加 `status: open`，全仓没有把 gate 置为 resolved/closed 的命令；`xr` 无 `resume` 动词。
- 影响：① 被 gate 的单元只能靠语义错误的 `xr fail` 复活；② `x-run-guard` 一旦看到“还有 open gate 且剩余单元全 blocked”就永远 `stop + handoff`，用户答复 gate 后也不会自动继续。
- 方案：加 `xr gate --resolve G<n> [--unit …]`，把关闭写回 `gates.md`，并把对应单元恢复为 `todo`。
- 风险：新增动词会扩大 CLI 合约；旧 `gates.md` 需要向后兼容读取。

### M7 `run_dir` 不校验 run id → 读写逃出仓库

- 位置：`xr:99-101`（`path = repo/".work-docs"/"runs"/name`，无格式校验、无解析边界断言）；`extensions/run-files.ts:9-21` 同构
- 证据（已复核）：把 `.work-docs/runs/ACTIVE` 写成 `../../../evil`、并在仓库外预置 `evil/RUN.md`（含 `xr:status` 标记块）和表头正确的 `units.tsv`，运行 `xr status`：

  ```text
  ok status   run: evil   units: 0
  仓库外 evil/RUN.md 被重写（hash 89ac09d1 → 289dcf95）
  ```
- 影响：只要 ACTIVE 被污染（误写、并发写、`xr import` 的副作用），状态写入会落在仓库外任意已有 `RUN.md` 的目录。
- 方案：用 `SLUG_RE` + 时间戳格式校验 run id，并断言 `path.resolve()` 落在 `.work-docs/runs` 之下。
- 风险：低。校验失败要给出可读错误（现在是 `找不到 run …`）。

### M8 `xr import` 失败仍报成功，且 `task_id` 未校验

- 位置：`xr:626-686`
- 证据（已复核）：contract 里写 `depends=w9`（未知依赖）→ `cycles()` 判真 → 跳过 `save_units` → units.tsv 只有表头，但 stdout 是 `ok import old-1 units=1`，`events.jsonl` 也记 `units:1`。
- 影响：静默空操作 + 假事实进事件流，审计面撒谎。
- 方案：`else: die(...)`；event 用实际写入行数；`task_id` 加 `ID_RE` 校验与目录边界断言（子代理取证：`xr import ../../../xrsecret/leak` 能读到工作区外 contract 并把内容搬进仓库）。
- 风险：`task_id` 校验会拒掉含大写/点号的旧任务目录名，需要确认现有命名。

### M9 `xr` 无文件锁 + 非原子写 → 并发丢更新、单次中断毁 run

- 位置：`xr:79-83`（`write_tsv` = `path.write_text`，截断后写，无 temp/fsync）、`372-441`（所有命令都是“读全表 → 改 → 整表覆写”）
- 证据：子代理实测 20 个并发 `xr next` → 同一单元被判 3 次、4 个成功回执最后只留下 2 行 doing；我复核 `grep -rn "flock|fcntl|O_EXCL" skills/x-rail/scripts/` 无命中、`grep -c "os.replace" skills/x-rail/scripts/xr` = 0。
- 影响：`xr next` 的核心承诺（不相交派发）在并发下不成立；任何 SIGKILL/磁盘满落在写入中途，整个 run 的 units.tsv 报废且没有修复路径（`plan add` 也要先 `read_tsv`）。
- 方案：照抄同仓 `coordination.py:71-80` 的 `temp + os.fsync + os.replace`；`next` 用 `.lock` + `fcntl.flock` 或 `O_CREAT|O_EXCL` 锁文件做原子 claim。
- 风险：引入锁需要超时与陈旧锁处理；Windows/非 POSIX 环境需降级方案（本项目目前只跑 macOS，可接受）。

### M10 安装测试假通过（bash 3.2 `[[ ]]` 不触发 `set -e` + 断言旧路径）

- 位置：`scripts/test-install-v3.sh:11-16, 24`
- 证据（已复核）：
  - `bash -c 'set -e; [[ -f /nonexistent-file-xyz ]]; echo REACHED_AFTER_FAILED_TEST'` → 打印 `REACHED_AFTER_FAILED_TEST`（本机 GNU bash 3.2.57）。
  - 实际安装布局是 `~/.pi/agent/extensions/x-rail/x-failover.ts`（decd5c7 之后），而断言写的是 `extensions/x-failover.ts`（不存在）。该脚本仍输出 `test-install-v3: passed`，退出码 0。
- 影响：安装布局回归无人看守；这是全仓唯一一处裸 `[[ ]]` 断言（其余 `check-workflow.sh`/`test-worktree.sh` 的用法都带 `&&`/`||`，语义正确）。
- 方案：断言改成 `[[ … ]] || { echo fail; exit 1; }`，路径改 `extensions/x-rail/x-failover.ts`；改完重跑整套脚本（可能连带暴露其它失效断言）。
- 风险：修好后可能立刻变红，需要预留修复窗口。

### M11 看门狗在工具执行期无限期暂停 → 卡死工具永不中止

- 位置：`extensions/x-run-guard.ts:67-73`
- 现象：`if (activeTools > 0) { lastTokenAt = Date.now(); arm(); return; }` —— 只要还有工具在跑，每 5 秒刷新一次计时，没有上限。
- 证据（已复核源码）：无上限常量；`constants.ts` 只有 `WATCHDOG_MS = 180_000`。
- 影响：这是 3c8488a 为修“同步子代理被误杀”引入的，但代价是任何挂死的工具（挂死的 bash、卡住的 xr）从此不会被中止，只能手动杀进程。
- 方案：记录工具开始时刻，暂停超过 `2×WATCHDOG_MS`（或按子代理超时阈值）仍触发 abort。
- 风险：阈值定太小会退回原缺陷（长同步子代理被误杀）；需要与 `stages/execute.md` 的 45 分钟上限对齐。

### M12 压缩摘要的模型请求没带对话内容

- 位置：`extensions/x-run-guard.ts:173-177`（`complete(model, { messages: [] }, …)`）
- 影响：“对话要点”补充段拿不到任何信息 —— 白付一次调用，并且这段时间压缩被阻塞最长 120 秒。
- 方案：传入 `event.branchEntries` 转换出的转录；或直接删掉补充段，只用 `xr capsule` 的胶囊。
- 风险：传全文会加大成本和延迟；120 秒超时降级要保留。

### M13 `lockedToFallback` 只置位不清零 → 自动切回永久失效

- 位置：`extensions/breaker.ts:41-43`（`open()` 里置位）、`83-85`（`noteFailback` 返回对象不含该字段）、`failback.ts:29`
- 影响：一旦发生“切回后 15 分钟内再次熔断”，此后**所有 run** 都永久留在兜底模型，而规格只要求“本 run”。
- 方案：`noteFailback` 里显式 `lockedToFallback: false`，或改成用 `lastFailbackAt` 的时间窗判断。
- 风险：直接清零会削弱“刚恢复就再挂”的滞回保护。

### M14 两个扩展共用 `agent_before_settle`，宿主是“后者覆盖前者”

- 位置：`extensions/x-failover.ts:105-171` 与 `x-run-guard.ts:90-140` 都返回 `{continue, entries}`；宿主语义见 `node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/runner.js:775-778`
- 现象：`entries = handlerResult.entries`（整体替换，不是追加）；`continue` 取最后一次赋值。
- 影响：① 两条续跑消息只能活一条（另一条“已切到 bai / 继续 run”的说明被吞）；② `x-run-guard` 的 `stop/handoff`（返回 undefined）挡不住 `x-failover` 的 `continue: true`；③ 同一个 `pending-boundary.json` 被两个扩展各自记账，同一边界可能压缩两次。
- 方案：确定唯一负责续跑消息的扩展，或把两边消息合并进同一条 entry；边界 nonce 只由一个扩展消费。
- 风险：合并需要跨扩展共享状态，复杂度上升。

---

## 3. 建议修问题

| # | 位置 | 现象 | 影响 | 方案 / 风险 |
|---|---|---|---|---|
| C1 | `SKILL.md:11-30` | 入口同时引用两套模型：routing→playbooks（task.py 证据模式），workflow→stages + `xr`，verification/recovery→task.py。**没有写“什么时候读 stages、什么时候读 playbook”** | 模型在同名 `plan`/`review`/`verification` 上随机选，两套语义互斥 | 入口加二选一判据，或明确 stages 取代 playbooks，或明确分区。风险：改动入口会影响所有路由 |
| C2 | `stages/*.md` 全文 + `install.sh` | 阶段卡写裸命令 `xr init/status/next/...`，但 `xr` 不在 PATH（`grep xr skills/x-rail/install.sh` = 0 命中） | 阶段卡第 2 步无法直接执行，模型只能猜 `<skill-dir>/scripts/xr` 路径 | install.sh 建符号链接，或阶段卡统一写全路径。风险：低 |
| C3 | `extensions/guard-core.ts:65,99` | 提示“输入 `/x-rail resume`”，但没有注册 resume 命令，`xr` 也无该动词 | 用户照做会失败 | 改文案为“读 capsule.md + `xr status`”，或实现 resume。风险：低 |
| C4 | `stages/execute.md:9` vs `modules/work-items.md:105`；`stages/plan.md:8` vs `playbooks/exec.md:32`；`modules/recovery.md:132` vs `stages/execute.md:12` | 子代理时限两套（45/25/15 分钟 vs “不另设运行倒计时”）；默认委派两套（<5 单元 main vs 默认委派）；失败阈值两套（重复 2 次/必过 3 次 vs 验证连续失败 2 次） | 同一体系内规则互相打架 | 各保留一处，其余给路径引用。风险：低（但要挑一处为准） |
| C5 | `references/failure-modes.md:9` vs `xr:487` | 文档承诺 `tool` 类失败“换模型后再试 1 次”，实现只把 state 回 `todo`，从不改 model 列 | 承诺的降级不生效 | 要么实现换模型，要么改文档为“同模型重试”。风险：低 |
| C6 | `xr:156-164`；`xr:167-172` vs `extensions/store.ts` | ① `breaker_open` 对 JSON 解析失败 `return False`（fail-open），限额从 2/1/2 静默放宽到 5/2/5；② `xr` 读 `X_FAILOVER_STATE` 环境变量，而扩展写 `~/.pi/agent/state/x-failover.json` 且从不设置该变量 → **xr 实际上永远看不到熔断状态** | 熔断时并发上限不生效；双份限额策略不同步 | 解析失败按“熔断打开”处理；扩展在设置状态时同步设置/传递路径，或让 xr 直接读默认路径。风险：改默认路径要兼容已有文件 |
| C7 | `extensions/guard-core.ts:76-89` + `xr:465-470` | `xr done` 写死 `dependsOnReasoning/unrelated/unattended = false`，没有其它写入者 → `boundaryDecision` 只会返回 `"compact"` | `continue`/`new-session`/`subagent` 分支不可达；**每个 `xr done` 边界都压缩一次**（成本 + 延迟） | 让单元携带这三个属性，或显式声明“边界一律压缩”并去掉死分支。风险：扩大 xr 接口面 |
| C8 | `xr:428-432` | 验证超时不杀进程组（同仓 `task.py` 用 `start_new_session=True` + `killpg`）；超时后证据文件 0 字节 | 泄漏后台进程；失败无诊断，违背 `execute.md` “原始输出落盘” | 抄 `task.py:run_verification` 的 session+killpg；超时分支按 bytes/str 双分支解码。风险：低 |
| C9 | `extensions/store.ts:28-38,55-64` | 无锁、tmp 名固定 `${file}.tmp`、解析失败静默清空全部熔断与 run 记忆、`runs` 无清理且每次工具调用全量重写 | 多会话/子代理并发丢更新；半截文件可能被 rename 上线；熔断记忆静默丢失；文件单调增长 | tmp 名带 pid；写前读-合并-写或加锁；损坏时上报。风险：加锁引入死锁/陈旧锁 |
| C10 | `x-run-guard.ts:31,62-88`、`run-files.ts:112-114`、`watchdog.ts:1-11` | 无 `session_shutdown` 清理定时器；`guard.json` 非原子写；看门狗标记是无时间戳单例且**优先于** `stopReason=aborted` | reload/换会话后旧定时器可能 abort 到新会话；guard.json 半写即静默清零续跑计数（绕过“连续无进展就停”）；用户 Esc 可能被记成 E5 → 自动切模型 + 续跑 | 监听 `session_shutdown`；guard.json 用 tmp+rename；标记加时间戳且用户中止优先。风险：中止优先需区分中止来源 |
| C11 | `references/verification.md`、`references/legacy-evidence-mode.md`、`references/external-skills.md`、`templates/long-task.md`、`templates/task-checklist.md` | 这 5 个文件不被任何 md 引用（孤儿）；入口也从不引用 `references/`、`templates/` 与其余 4 张 stage 卡 | “按需加载”最受益的一层事实上不可达 | 入口补索引，或删除。风险：低 |
| C12 | `install.sh:43-49,73-85`；`README.md:39` | ① `--no-backup` 且目标已是真实目录时，`backup_path` 直接返回，随后在**目录内部**建同名软链，脚本仍报“已链接”（已复核复现：`skills/x-rail/x-rail -> …/worktrees/v3/skills/x-rail`）；② 无卸载/回滚脚本，只有 `v3-backup-<时间戳>/`；③ 在 worktree 里运行会把 `.worktrees/v3/...` 绝对路径写进 `~/.pi`，worktree 一删安装全断 | 静默装错；回滚只能手工 mv | 已存在且非目标软链时直接报错退出；加 `--rollback`/README 说明；拒绝在 worktree 安装或显著提示。风险：中 |
| C13 | `extensions/subagent.ts:10-26` | `concurrencyLimits`/`dispatchModel`/`reviewerFamily` 无运行时消费者（只有测试引用） | “熔断减半 / 评审换模型家族”实际靠模型照文档自觉，代码不保证 | 接进派发路径，或明确写成“提示词约定”。风险：接进去要改技能/子代理接口 |
| C14 | `scripts/test-xr.py:78,123-138`；`failover.test.ts:5-14` | ① `assertNotRegex(units, r"^c\t.*\tdoing\t")` 缺 `re.M`（已复核：`^` 只匹配首行）→ 断言恒真；② 名为“并发减半”的测试用 `subprocess.run` 串行调用，结构上不可能发现重复派发；③ 扩展的事件接线（`x-failover.ts`/`x-run-guard.ts`/`run-files.ts`/`watchdog.ts`）零覆盖；④ `test-mock26.mjs` 只验证 mock 服务自身，不经过任何 failover 代码 | 核心并发承诺与事件接线都没有测试看守 | 断言加 `re.M`；用真并发重写；补一个驱动 handler 的集成测试；把“mock26 通过”措辞改成“mock 服务自测”。风险：集成测试要 mock ctx，成本不低 |
| C15 | `xr:626-686` | `xr import` 每次都 `cmd_init` 新建 run 并改写 `ACTIVE` | 同任务重复导入产生孤儿 run，记账被弃 | 同 task_id 已导入过则复用或拒绝。风险：低 |
| C16 | `xr:527-534, 540-544` | gate 去重是**子串匹配**（`if f"- question: {text}" in text`，已由子代理复现“要不要”被“要不要改接口”吞掉）；且先写 `gates.md` 再校验单元，单元不存在时留下永久脏 gate | 丢问题；状态永久错误 | 用行精确匹配；先校验全部入参再落盘。风险：低 |
| C17 | `xr:135-152` | 未知依赖被 `cycles()` 报成“依赖有环” | 错误信息误导排障 | 区分 unknown dep 与 cycle。风险：低 |

---

## 4. 备注

- N1 `xr:454-461`：`done` 的幂等短路在 verify 校验之前 —— 树变了仍报 `unchanged`。属设计上的“不回头”，建议在 RUN.md 里写明。
- N2 `events.jsonl` 只追加，无轮转。
- N3 `.work-docs` 整目录被 `.gitignore` 排除 → VERIFIED 的 ledger 不进版本库，clone 后无法复核。
- N4 `plans/v3/03-技术方案.md:54` 提到 ledger verdict 有 `INCONCLUSIVE`，实现只产出 VERIFIED/FAILED。
- N5 `xr:409-441`：`verify_cmd` 来自 units.tsv，用 `shell=True` 在仓库根执行 —— 等于 units.tsv 是代码执行载体。属设计意图，但要清楚这一点。
- N6 `extensions/constants.ts:4-6`：模型名（`openai26/gpt-6.1-sol`、`bai/deepseek-v4.1-flash`）硬编码；用户换模型即失效。
- N7 交付物分散：v3 设计与验证文档在 `plans/v3/`，而早期一轮（task.py 协调模块）在 `plans/refactor-2026-10/`；`delivery.md:24` 把基线 `b158f20` 写成“基线/HEAD”，实际 HEAD 是 `3c8488a`（子代理取证）。
- N8 `install.sh` 只装 4 个技能，`runtime-skills.txt` 列了 ~35 个（另一个 install 脚本的范围）—— 两套安装范围并存，需要明确 v3 之后以哪个为准。
- N9 `self_check.py --skills-dir ~/.pi/agent/skills` 会提示缺 7 个外部技能（tdd、code-review、diagnosing-bugs、research、domain-modeling、grilling、codebase-design）。**已复核：这些技能实际装在 `~/.agents/skills`，可正常调用**，所以这条是目录选择的提示，不是真缺失。

---

## 5. 通过项（正向事实，均已复核）

| 项 | 结果 |
|---|---|
| `python3 scripts/test-xr.py` | 5 tests OK |
| `bash scripts/typecheck-extensions.sh` | passed（`@earendil-works/pi-coding-agent@1.3.0`，3 个入口都在编译集合内） |
| `bash scripts/test-failover.sh` | `failover tests passed` + `mock26 tests passed` |
| 入口体量 | SKILL.md 4,545 字节（目标约 5KB，达成）；`self_check.py` 报“体量通过 入口=4545” |
| 宿主 API 用法 | `agent_before_settle`/`tool_result`/`session_before_compact`/`getContextUsage`/`setModel`/`compact`/`modelRegistry` 等事件与方法在 1.3.0 类型定义中均存在 |
| 扩展加载布局 | `pi.extensions` 清单只声明两个入口，辅助模块放子目录 → 不会被当扩展加载（已实测安装布局） |
| `install.sh` 幂等性 | 二次运行输出全为“已是目标软链/扩展未变化/清单未变化”，文件集 SHA 一致 |
| `install.sh` bash 3.2 兼容 | 无关联数组（5510839 即为该修复） |
| 阶段卡与实现一致性 | 并发 5/2/5、熔断 2/1/2、timebox 默认 45/25/15、capsule ≤2048 字节、`init/decide/gate/status` 参数形状均与 `xr` 一致 |
| 上报流程的诚实度 | `plans/v3/verification-report.md` 自己写明“没有第二模型家族的审查”“没有调用付费模型”“指标不填实测” —— 这三条我复跑命令后确认数字属实，未发现虚报 |
| `xr` 无无界重试 | `attempts < 2` 上限；`verify` 有超时；协调模块无自动重试 |

---

## 6. v3-goal 第九节验收标准逐条判定

| # | 标准 | 判定 | 依据 |
|---|---|---|---|
| 1 | 入口约 5KB，只承担入口路由 | **部分满足** | 4,545 字节达成；但入口还含 authority/budget/recording/loading/decision_policy/verification/recovery/output_contract 8 段，其中 budget/verification/recovery 在 modules 里又写一遍 |
| 2 | 详细规则按需加载 | **满足** | stages/modules/playbooks/references/templates 分层存在 |
| 3 | 不存在靠拆文件增加总复杂度的假优化 | **不满足** | `skills/x-rail/**` md 总量 109,854 → 136,461 字节（+24%）；且两套任务模型并行、同名卡语义互斥（C1/C4） |
| 4 | 任务状态不依赖聊天上下文 | **满足** | `xr` 全部状态落盘 `.work-docs/runs/<id>/`（RUN.md/units.tsv/ledger.tsv/decisions.tsv/gates.md/events.jsonl/capsule.md） |
| 5 | 普通任务默认不启动子代理 | **不满足（已记录替代决策）** | `SKILL.md:10`、`playbooks/exec.md:32`、`modules/work-items.md:72` 都是默认委派；`stages/plan.md:8` 是 <5 单元 main。DECISIONS C1 已明文“放弃 v3-goal 原文‘子代理默认关闭’”，属已知偏离，但入口没有写判据 |
| 6 | `task.py` 是可选检查器、不是完成门 | **不满足** | `SKILL.md:29` 把 task.py 完成系列为证据模式依据；`modules/verification.md` 以 finish/complete 为门；只有 `references/legacy-evidence-mode.md:3` 说不看 |
| 7 | API 瞬时错误最多自动重试 1 次 | **部分满足** | `xr:487` `attempts < 2`；`decideSwitch` 同模型重试各 1 次；但 `config/examples/1.2-retry.jsonc` 未安装（需用户手工并入 settings），且 provider 层重试与 xr 层重试可叠加 |
| 8 | 工作项不会无限运行 | **部分满足** | `opera` 看门狗 180s（但 M11 使其在工具期失效）；`stages/execute.md:9` 45/25/15 分钟；`modules/work-items.md:105` 却明文禁止设时限 |
| 9 | 旧格式/旧脚本/旧任务迁移策略明确 | **部分满足** | `xr import` 提供迁移；但 `references/legacy-evidence-mode.md` 与 `templates/long-task.md` 是孤儿文件，入口不可达 |
| 10 | 关键操作可重复执行 | **部分满足** | `done`/`status`/`decide` 幂等；`import` 非幂等（C15）；`gate` 去重不严（C16） |
| 11 | 失败后能保存恢复信息 | **部分满足** | `handoff.md` + capsule 有；但 M2/M6 会产生永久阻塞态，且 handoff 文案指向不存在的 `/x-rail resume` |
| 12 | 有 pstack 对比 / 提交分析 / 指标对比 / 可执行验证 / 独立审查 / 残余风险清单 | **部分满足** | 前四项与残余风险齐备（`plans/v3/*`、`plans/refactor-2026-10/*`）；**独立审查缺失**（`verification-report.md` 自述“没有第二模型家族的审查”，`delivery.md:55` 自述“修复后独立审查尚待父会话执行”）；真实回放（`--live`）未跑 |

---

## 7. 未验证 / 无法确认

1. **真实模型行为**：T1–T8 回放从未跑（`evals/replay/harness.py --live` 退出码 2，是门闩不是执行器）；模型服从率、成本、跨日稳定性、API 长尾改善都没有实测。
2. **宿主运行期行为**：扩展真实加载、看门狗实际中止、`setModel` 生效性只能确认文件就位与类型匹配，没有真会话取证。
3. **真实会话日志**：`evidence.md` 记“无法取证真实会话错误”；`plans/refactor-2026-10/v3-挑战.md` 记“真实任务都失败了”，只给了两个会话 ID，未附具体失败串。
4. **`pi-subagents` 接口**：`agentOverrides` 键名、单个代理能否设 `toolBudget`、子 pi 进程是否加载 `~/.pi/agent/extensions` —— `IMPL-REPORT.md` 自己列为未决。
5. **`task.py`/`task_checks.py` 内部**：只做了交叉引用检索，未逐行审查完成门实现（本轮重点是 v3 新增层）。
6. 未跑：`test-flow.sh`、`test-install.sh`、`test-skill-metadata.sh`、`test-document-template.sh`、`check-repo.sh`；未重跑 `refactor-2026-10` 的 closeout 系列日志（只抽查 6 个，均自洽）。

## 8. 建议行动顺序

1. 先修 M1、M2（扩展会主动伤害正常会话，且不可逆地影响用户对“自动续跑”的信任）。
2. 再修 M3、M4、M5、M6、M7、M8（`xr` 的完成门与状态边界；这几条互相独立，可并行）。
3. 修 M9（锁 + 原子写）——它是 C9/C12 同类问题的根，改法可复用 `coordination.py` 的既有实现。
4. 修 M10，然后重跑整套脚本，把连带变红的断言一起处理。
5. M11–M14 与 C 组一起：先定 C1（入口两套模型的判据）与 C4（时限/委派/阈值的唯一出处），否则改哪一处都会和另一处打架。
6. 补独立审查与一次真实回放：`verification-report.md` 和 `delivery.md` 都自述缺这一环，这是 v3-goal 明确要求的验收项。

## 9. 审查过程说明

- 本体实测命令全部在临时目录或只读路径执行，未触碰仓库文件（唯一写操作是 `mktemp` 里跑 `install.sh` 与 `xr`）。
- 三个子代理的输出分别保存在会话 artifact 目录；本报告中标注“子代理取证”的条目未由我二次复现，其余“已复核”条目均为我亲自执行并保留输出。
