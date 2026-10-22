# v4 双轴审查（Standards / Spec）

- 仓库：`/Users/yuanxj/Documents/github/x-rail/.worktrees/v4`，分支 `v4`
- 范围：`900ae74^..HEAD`（固定点 `900ae74^` = `9f89a85`）+ 工作区未提交改动（`DECISIONS.md`、`plans/v4/05-实施与验收计划.md`，共 +12/−2）
- **注意**：任务描述说 6 个提交，实际 `git log 900ae74^..HEAD` 是 **9 个**（另有 `1dffceb`、`50b62cf` 两次 compact 探针与小修订），已一并审阅
- 只读：未改文件、未联网、未安装、未提交
- 实际跑过的命令：
  - `node plugins/pi-model-recovery/decide.test.ts` → `model-recovery decide tests passed (31)`
  - `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-xr.py` → `Ran 38 tests ... OK`
  - `bash scripts/test-package-v4.sh` → `package test: passed`
  - `bash scripts/package-v4.sh --dest /tmp/... --dry-run` → 70 + 4 个文件，两清单互斥
  - 临时仓库只读行为探针（`/tmp`）：`xr capsule` 无 `XR_SESSION`/`PI_SESSION_ID` → `xr: session 与当前绑定不一致，拒绝旧会话写入`、`rc=2`；`xr acceptance set A1 ... --source session:abc#entry:xyz` → `ok acceptance A1 set`
  - 未跑：`scripts/typecheck-extensions.sh`（缺依赖时脚本会 `npm install`，属联网，禁止）、`scripts/test-run-lifecycle.mjs`（需真实 Pi 宿主，未在允许清单）

## 标准源清点

| 期望标准源 | 结果 |
| --- | --- |
| `AGENTS.md` | **不存在**（`git ls-files` 无此文件，主工作区也无）。标准轴改用下列三份 |
| `skills/x-rail/SKILL.md` | 存在，但未随 v4 改动（仍是 task.py 路由，见 Spec F2） |
| `docs/file-boundary.md` | 存在，本次 +11 行（新增 v4 run files 段） |
| `plans/v4/DECISIONS.md` | 存在，本次重写 |

Fowler 基线（Mysterious Name / Duplicated Code / Feature Envy / Data Clumps / Primitive Obsession / Repeated Switches / Shotgun Surgery / Divergent Change / Speculative Generality / Message Chains / Middle Man / Refused Bequest）对 diff 全文适用，结果见下。

---

## Standards

### 硬违规（与仓库文档明文冲突）

1. **扩展绕过运行锁直接写运行目录状态。**
   `docs/file-boundary.md`：v4 run files「只由 `xr` 在运行锁内写入」。实际：
   - `skills/x-rail/extensions/x-run-guard.ts:251` 用 `writeAtomic` 直接写 `handoff.md`；
   - `skills/x-rail/extensions/run-files.ts:231-233` `saveGuardMemory` 直接写 `guard.json`（`x-run-guard.ts:219` 调用）。
   两处都没有 `run_lock`、没有 `check_writer` 的 session/generation 校验，也没有 epoch。`plans/v4/03` 「所有任务权威状态写入均在现有 `run_lock` 下」被同时违反。

2. **`docs/file-boundary.md:15-20` 的 v4 运行文件清单与实现不一致。**
   清单没有 `guard.json`、`pending-boundary.json`、`decisions.tsv`、`gates.md`、`closed`、`finish.invalid.json`，但代码都在写/读这些文件（`xr:1298 write_binding`、`xr:1174-1197 close`、`x-run-guard.ts:219`）。清单是「允许写入的文件边界」，漏项使其失去约束力。

3. **类型直转绕过校验，违反 03 的「类型客户端必须实际校验而非直接强转」。**
   - `plugins/pi-model-recovery/decide.ts:127` `keyOf(input.failed as ChainEntry)`（`failed` 的 `provider`/`model` 都是可选的）；
   - `plugins/pi-model-recovery/index.ts:123` `request.failed?.message as { stopReason?: string }`；
   - `skills/x-rail/extensions/x-run-guard.ts:147` 直接读 `event.preparation.firstKeptEntryId`，没有结构校验、没有缺字段降级。
   对照 `run-files.ts:137-155` 的 `validInspectSnapshot`（写得很完整）：同一 repo 两套标准。

4. **解耦后仍保留对已移除依赖的误导性理由。**
   `skills/x-rail/extensions/guard-core.ts:30`：`{ action: "ignore", reason: "provider 错误交给 x-failover" }`。守卫已声明独立于 failover（DECISIONS 2026-10-22 D1），注释/文案仍把职责推给它。

5. **注释、文件头命名仍是 v3。**
   `skills/x-rail/scripts/xr:2` docstring「xr：v3 run 的记账命令」；`skills/x-rail/install.sh:2`「x-rail v3 的 4 个技能软链和两个扩展」。v4 交付物仍自称 v3。

### 判断项（基线 smells，按 hunk）

- **Duplicated Code** `plugins/pi-model-recovery/index.ts:95-101`：`/model-recovery` 命令的三元分支两支完全相同，`args` 实际未用；同一段逻辑写了两次。
- **Speculative Generality** `plugins/pi-model-recovery/index.ts:93` `let active` 只赋值一次（应 `const`）；`guard-core.ts:80 compactText(capsule, supplement)` 的 `supplement` 在所有调用点恒传 `null`（`x-run-guard.ts:147,224`）——为不存在的调用者留参数。
- **Message Chains** `skills/x-rail/scripts/xr:130,155,1347` 三处 `run.parent.parent.parent` 手工推算仓库根；应抽一个 `repo_of_run(run)`，否则改目录布局要改三处。
- **Mysterious Name / Primitive Obsession** `skills/x-rail/scripts/xr:724`：人工证据把 `input_scope` 存进 `cmd` 列、把 `input_scope` 再复制进 `input_scope` 列（`item["cmd"] = input_scope`）；ledger 的 `cmd` 列在 command 语义是命令、在 observation 语义是路径，`verified_now` 又只比 `cmd_hash` 不比 `cmd`（`xr:840`）。建议加 `scope_kind` 或改名。
- **Repeated Switches** 三种 `evidence_kind` 的分派散在 `cmd_evidence`（648）、`cmd_verify`（731）、`verified_now`（815-843）三处；B3 只统一了摘要函数（`verification_hash`），kind 分支没统一。
- **Duplicated validation** `skills/x-rail/scripts/xr:1512-1530`（`cmd_receive` 读回执）与 `xr:181-201`（`cmd_event` 读记录）是同一套「非 file/JSON 解析/非对象」模板。
- **Speculative Generality（死代码随包发布）** `scripts/package-v4.sh:32` 只排除 `x-failover.ts`/`failover.test.ts`，`breaker.ts`、`classify.ts`、`switch.ts`、`store.ts`、`compat.ts`、`failback.ts`、`subagent.ts` 全部打进包，而守卫 `x-run-guard.ts` 一个都不 import。包体多 8 个死文件。
- **手写 JSON** `scripts/package-v4.sh:82-92` 用 `printf`/`awk` 拼 manifest；文件名含 `"`/`\` 会产出坏 JSON（当前文件集安全，但这是可避免的手写序列化）。
- **静默失败** `skills/x-rail/extensions/run-files.ts:196-205` `refreshCapsule` 全捕获，错误被吞；调用方（`x-run-guard.ts:144,209`）据此认为胶囊新鲜。
- **工具链与「不联网」冲突（存量，被本 diff 强化）** `scripts/typecheck-extensions.sh:5-7` 缺 `node_modules` 时自动 `npm install`。本次因此无法运行该脚本；CI 想在离线环境跑就会破功。
- 跳过：`scripts/test-xr.py` 里 `self.assertEqual(...)` 一行断言的长链、`XrTests` 方法名重复前缀，属工具/风格层面，未逐条列。

---

## Spec

对照 `plans/v4/03-x-rail任务闭环.md`、`04-Pi模型恢复插件.md`、`05-实施与验收计划.md`。

### A. 实现了但被要求不做 / 做错

1. **会话引用来源只校验格式就当作已验证。**
   03：「来源是会话引用时，不能只检查引用格式就当作已验证来源…标为“来源待核实”，禁止自动完成」。
   代码：`skills/x-rail/scripts/xr:1374-1378`（`source_ref` 只做正则）与 `xr:1390-1394`（`source_ok` 对 `session:` 仅 `fullmatch` 即返回 `True`），`xr:1661` 直接计入 `covered`。**实测**：`xr acceptance set A1 "有来源" --source session:abc#entry:xyz --units u1` → `ok acceptance A1 set`；该验收随后可被算作已覆盖。「来源待核实」这个状态根本不存在。

2. **「守卫满足判据就调用 finish 生成收据」没有实现。**
   03「任务级停止规则」：`finished` 前「同一绑定若在正常结束时满足全部判据，任务守卫调用 finish 并生成当前收据」。
   代码：`skills/x-rail/extensions/x-run-guard.ts:196` 把 `doneMet` 送进 `shouldContinue`，`guard-core.ts:38` 直接 `ignore`；`grep -rn "finish" skills/x-rail/extensions/*.ts` 无任何命中。收据只能手动 `xr finish`。05 的 D 行未标注此缺口。

3. **压缩仍然用「仅含胶囊的自制 compaction」替换宿主摘要。**
   03：「胶囊为可重建摘要，不能替换整个 Pi 压缩摘要…补充接口若不可用则只附路径，不返回仅含任务胶囊的自制 compaction」。
   代码：`x-run-guard.ts:142-150`（`session_before_compact`）返回 `{compaction:{summary: capsule}}`，`supplement` 硬编码 `false`；`x-run-guard.ts:224` 在 before_settle 里 push `{type:"compaction", summary: compactText(capsule,null)}`。更糟：`refreshCapsule` 无 session（实测 `rc=2`），胶囊多为空，摘要就变成「胶囊缺失，先执行 xr capsule」——把整段对话上下文压成一句话。
   05 最新一行已诚实记为「摘要路径本身未验证 / 宿主拒绝 compact」，但代码方向与 03 的禁止项相反，不只是「未验证」。

4. **网关错误改写不限定「当前会话选中本插件虚拟模型」。**
   04 错误边界：「仅处理实际失败的 assistant 消息，**且当前会话选择本插件虚拟模型**」。
   代码：`plugins/pi-model-recovery/index.ts:151-160` 只要有 `gatewayCompatibility` 就改写 `errorMessage`，不看 `ctx.model`。物理模型会话里被加上「temporary gateway error」标记后，宿主若据此重试，重试的仍是同一个物理模型——插件因此可能凭空制造额外付费请求，而 04 明确「不请求一次健康探测」。

5. **route 不区分鉴权/余额/未知错误。**
   04 表格：「鉴权、余额不足、额度耗尽、权限错误 → 不改写、**不切换**」。
   代码：`index.ts:110-141` 在 `reason==="retry"` 时只用 `failed.model` 选下一个模型，不看 `failed.message` 文本；`decide.ts` 也没有 non-transient 短路。若宿主对 401/余额错误发起 retry，插件会静默换链，正是 04 禁止的「用备用模型绕过费用/凭据问题」。E1 只测了 `markGatewayError` 不改写，没测 route 不切换。

6. **`/model-recovery status` 未显示分支冷却与当前虚拟选择。**
   04：「显示配置路径、有效链、当前虚拟选择、分支冷却与宿主重试设置」。
   代码 `index.ts:74-90` 显示的是 **配置里的** `cooldownMs`，不是 `BranchState.cooldownUntil`/`activeIndex`；「当前选择」取命令执行时的 `ctx.model`，不是分支状态里的当前索引。05 也把这条留到「E2 剩余」。

### B. 声称完成但证据/路径不支持

7. **D2「会话身份变化时才重绑并递增 generation」不可达。**
   05 D2 行与 DECISIONS「agent_start 时校对会话 id，不同才重新 bind（generation 递增）」。
   但 `xr:1919` `cmd_bind` 在 `binding.session_id != --session` 时直接 `die`（要求 `resume --take-ownership`），而 `x-run-guard.ts:98-108` 调的正是 `bindRun`→`xr bind`；DECISIONS 自己又记「`new_session` 会重置扩展模块状态」→ `bound` 被清空，`agent_start` 的 `if (bound && …)` 分支根本不会进。结论：重绑分支既不可成功也不可达，测试名 `session switch stops the old session…` 只验证了「不重绑」，没验证「重绑成功并递增」。

8. **05「C4 审查会话须属当前工作区、非实现会话，且报告文字出现在其助手输出」被高估。**
   代码只校验：首行 `type=session` + `cwd==repo` + `id` 不在 `implementation_sessions()` + 报告文本出现在任一 assistant `text` 里（`xr:681-706`）。任何实现者都能手写两行 JSONL 通过。DECISIONS 已声明「不验证签名，不声称防伪造」——但 05 的验收措辞读起来像身份已验证。评审措辞应降级为「未验证来源」而不是「独立审查」。

9. **「receive 核对宿主终态」的可信起点是模型可写的事件。**
   05 C2：「`receive` 核对宿主终态、进程退出、子会话、输入及输出」。但 `worker_started` 事件可由模型自己 `xr event` 写入（`xr:206-208` → `prepare_worker`），`status_path` 就来自该事件；随后模型可自造 `status.json`（`state: complete`、`exitCode: 0`、session 文件首行），`cmd_receive` 全部接受。真实探针路径可信，检查器本身不构成不可伪造证据；03 已声明「回执只证明已启动」，但 05 的措辞超出这一点。

10. **`plans/v4/00-README.md:3` 状态过期。**
    「状态：**新设计基准；仅方案，未授权实施、安装或发布**」，同文件还引用代码提交 `9f89a855…`；而本分支已有 9 个实施提交并把 A–F 记录进 05。00-README 是入口文件，读者会得到相反结论。

### C. 确认成立（抽样复核，未发现问题）

- C4 证据不可覆盖：`xr:719-724` 独占创建 + `report_hash` 绑定，`xr:677-678` 有效期内拒绝重录；篡改 `notes/` 副本后 `done` 拒绝（38 项测试覆盖）。
- C4 绑定输入与最终产物：observation 绑 `verification_hash`，review 绑 `review_input_hash`（`xr:805-812`，含所有非 review 单元摘要 + `acceptance.tsv`）。
- C4 `review_required` 真挡完成：`xr:1697` + `xr:1801-1815`（`cmd_finish` 走 `inspect_data`）。
- B4 身份/代次：`xr:125-148 check_writer` 校验 workspace/run/session/generation/lease；旧代次写入实测拒绝。
- C1 事件去重与未决副作用：`xr:203-205` 去重；`op_result` 仅 success 关闭动作（`host-events.ts:79-87`）。
- E2 配置无效不注册虚拟模型、零请求：`index.ts:106-109` 提前 return，`scripts/test-model-recovery.mjs` A/B 两段断言。
- F1 拒绝覆盖：`scripts/package-v4.sh:22-25` + `scripts/test-package-v4.sh` 实测通过。

### D. 打包专项（漏数据 / 静默覆盖）

- **按包自带的 install.sh 装不出可用守卫**：`skills/x-rail/install.sh:29` 的 pi 清单只有 `"./x-failover.ts"`，`install.sh:38` 的 `EXT_FILES` 也含 `x-failover.ts`；而 `scripts/package-v4.sh:32` 把该文件排除。导出包执行 install.sh 会在 `install.sh:88-89` 以「缺少 x-failover.ts」退出 1。同时清单里没有 `x-run-guard.ts`，即「只打包任务守卫」不成立。F2 要求的「安装文件列表、Pi manifest 一致性反例断言」未做。
- manifest 的 `entry` 指向包内不存在的路径：`package-v4.sh:90-91` 写 `skills/x-rail/SKILL.md`、`plugins/pi-model-recovery/index.ts`，包内实际是 `x-rail/SKILL.md`、`model-recovery/index.ts`；测试 `test-package-v4.sh:32` 反而断言前缀是 `skills/x-rail/`，把错误固化。
- `assert_clean`（`package-v4.sh:44-50`）只精确匹配 `auth.json`/`.env`：`.env.local`、`.envrc`、`*.pem`、`id_*`、`credentials.json` 都会漏过；`list_files` 还静默丢弃 `*.log`。
- `shasum`（`package-v4.sh:40-41`）只在 macOS 存在，Linux 跑 `test-package-v4.sh` 会失败。
- 静默覆盖只靠 `[[ -e "$DEST" ]]`（`package-v4.sh:22`）：悬空软链不命中 `-e`，之后 `mkdir -p`/写文件会跟随软链写到别处。
- 未见运行数据泄漏：包内无 `.work-docs`、`plans`、`node_modules`、`.pyc`（dry-run 已核）。

---

## 汇总

- Standards：硬违规 5 条、判断项 10 条。
- Spec：被要求不做/做错 6 条、声称超出证据 4 条、成立项 7 条、打包专项 6 条。
- 各轴最严重：
  - Standards 最严重：扩展绕锁直写 `handoff.md`/`guard.json`（破坏「唯一写者 + generation 防旧写」这条基础不变量）。
  - Spec 最严重：`session:` 来源只校验格式即计入完成（03 明文禁止、实测可绕过），以及守卫用被接管会话的身份继续推进（`automation_allowed` 不比对调用者身份）。
