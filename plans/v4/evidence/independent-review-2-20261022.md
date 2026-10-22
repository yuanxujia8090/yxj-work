# v4 第二轮复审：审查后修复（19f04ea / d7f4a0e / 42af497 + 当前 HEAD）

- 仓库：`/Users/yuanxj/Documents/github/x-rail/.worktrees/v4`（分支 `v4`）
- 复审范围：`19f04ea^..HEAD` + 工作区未提交改动（`DECISIONS.md`，+7）
- **HEAD 在审查期间被并发推进**：开始时 `42af497`，审查中变为 `0aebbf4 fix(v4): break finish deadlock and add offline simulation`。本报告按 **当前 HEAD `0aebbf4`** 复核（含该新提交，因为它正好改了 `finish` 与守卫收口），并已标注该提交引入的新问题。
- 只读：未改仓库文件、未联网、未安装、未提交。所有探针都在 `/tmp` 临时目录与临时 HOME 中执行。
- 实际跑过：
  - `node plugins/pi-model-recovery/decide.test.ts` → `34 passed`
  - `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-xr.py` → `Ran 40 tests ... OK`
  - `bash scripts/test-package-v4.sh` → `package test: passed`
  - `bash scripts/test-install-v3.sh` → `passed`
  - `/tmp` 探针：完整跑 `xr init/plan/next/verify/done/evidence/acceptance set/inspect`，验证 `session:` 来源能否用**不存在的 entry + 不相关单元**通过覆盖
  - `/tmp` 探针：`install.sh --home <tmp>` 后检查 `xr` 是否能被已安装扩展解析、残留 `x-failover.ts` 是否被清理

## 结论

**有条件可交付。** 第一轮 5 条阻塞中 3 条真修好（`xr guard set` 落锁写、网关标记限定虚拟模型会话、打包 manifest 相对入口），2 条只是部分修复（`session:` 来源、压缩摘要），另有 2 条新发现会直接造成“装好了但不工作 / 静默停摆 / 静默放弃换链”。

---

## 逐项结论（对应任务里的 6 个重点）

### 1. `xr:1390 source_ok` 的 session 分支 —— **部分成立，仍可绕过**

成立的部分：只匹配格式已经不再算数，必须有 `notes/` 下、由 `ledger.tsv` 记录过、`observer` 等于该会话 id、`session_hash` 非空的副本。

仍可绕过（实测）：

- **`#entry:` 里的 entry id 完全不校验**，随便写 `entry:THIS-DOES-NOT-EXIST` 也通过。
- **报告与单元不对应**：只要 run 里有任意一条 review 证据（哪怕是为单元 `r` 建的），任何验收行的 `--source session:<同一会话>#entry:<任意>` 都被算作“有来源”。实测把 `--units i`（已 done 的命令单元，与审查单元 `r` 无关）配合伪造 entry id，`acceptance_status.covered` 直接变成 `1`。
- 代码位置：`skills/x-rail/scripts/xr:1390-1410`（`source_ok`），消费点 `xr:1693`（`inspect_data` 的 `covered` 判断）。

对照 spec：`plans/v4/03-x-rail任务闭环.md:40`「来源是会话引用时，不能只检查引用格式就当作已验证来源……旧引用标为“来源待核实”，禁止自动完成」。现在既没有“待核实”状态，也没有把引用定位到具体消息。

`run` 参数本身：**唯一调用点 `xr:1693` 已传 run**（`xr:1677` 旧行号对应新 `1693`），`run is None` 时保守返回 False，没有漏传。

### 2. `x-run-guard.ts` stale-binding / finishRun / saveGuardMemory —— **有误伤与两处文案/行为不一致**

- **不会**在同会话、generation 未变时误伤：`bound.generation` 与 `snap.binding.generation` 都来自同一份 `binding.json`，没有第三方写入时必然相等。
- **会**在同会话、generation **合法递增**时误伤：`xr resume --confirm`（`xr:1937` 无条件 `generation += 1`）和手工 `xr bind --session <同一会话>`（`xr:1967` 同样无条件 +1）都会让守卫判 `stale-binding`，然后 `bound = null`（`x-run-guard.ts:178-182`）。之后 `session_start`/`agent_start` 都不会再重绑（`agent_start` 只在 `bound && sessionId 变了` 时尝试，`x-run-guard.ts:99`），**本进程内守卫永久停摆**，只能重启 Pi。用户正常“暂停→resume 恢复”的路径会顺手把守卫关掉，且只有一个 warning。
- `finishRun` 失败：**确实不会继续跑**（返回 `undefined`，不返回 `continue`），这点成立；但提示写“请看 handoff”（`x-run-guard.ts:196`），而该分支**没有调用 `stopWithHandoff`，不会写 `handoff.md`**，用户在磁盘上找不到它说的文件。
- `saveGuardMemory` 失败分支：**没有漏写 handoff**，`x-run-guard.ts:232-233` 走的是 `stopWithHandoff`，会写 `handoff.md` 并记 `handoff`/`handoff-failed` 事件。这条成立。
- 新增的 `onlyReceipt` 分支（`x-run-guard.ts:191-198`）在“只剩 `receipt:stale/invalid`”时会调 `xr finish`，这条本身正确（`cmd_finish` 只把非 `receipt:` 问题当阻塞，`xr:1874`）。但它在 `lease=paused` / `phase=paused` 时同样会执行（`finish` 没有 phase/lease 门槛），并且用户暂停后每次 settle 都会重复 `finish`、重复 `epoch+1`、重写 `finish.json`。

### 3. `session_before_compact` 去掉 compaction —— **`session_before_compact` 改对了，但同一个“胶囊当摘要”的写法还在另一条路径上**

- `x-run-guard.ts:142-147` 现在只刷新胶囊 + 记事件，不返回 compaction。文档 `docs/v4-task-guard-and-model-recovery.md:49-55` 也没承诺胶囊进摘要。这一段与文档一致。
- **但 `guardBoundary` 里仍然在自造 compaction**：`x-run-guard.ts:237-239`
  ```ts
  const capsule = readCapsule(bound.dir) || `run ${bound.runId}：胶囊缺失，先执行 xr capsule。`;
  entries.push({ type: "compaction", summary: compactText(capsule, null), firstKeptEntryId: null });
  ```
  `compactText(capsule, null)` 就是“只有胶囊”的摘要，正是第一轮 Spec 第 3 条与 03 文档禁止的形态。也就是说：`session_before_compact` 不再覆盖，但 token 超阈值时 `agent_before_settle` 仍会把整段上下文换成一段胶囊（或一行“胶囊缺失”）。
- 雪上加霜：`refreshCapsule`（`run-files.ts:202-212`）调用 `xr capsule --repo <cwd>`，**没有 `--session`/`X_RAIL_XR`**；`xr capsule` 走 `run_lock` → `check_writer` 要求 session。探针已确认无 session 时 `rc=2`。调用点 `x-run-guard.ts:220` **丢弃了返回值**，随后 `readCapsule` 读到的是旧胶囊。压缩/续跑用的可能是过期胶囊。
- “压缩后能否恢复”：不返回 compaction 后，宿主摘要由 Pi 生成，胶囊只作磁盘材料，agent 靠 `resumeHint`/`capsule.md` 恢复——这条通，但依赖胶囊本身被正确刷新，而上面两点让它不可靠。

### 4. `plugins/pi-model-recovery/index.ts` —— **虚拟模型限定成立；`failedTextOf` 会误判；`state` 语义变得更脆**

- `markGatewayError` 现在只在 `ctx.model` 为本插件虚拟模型时执行（`index.ts:166-167`），符合 04「仅处理……且当前会话选择本插件虚拟模型」。成立。
  - 未验证点：失败那一轮 `ctx.model` 报的是虚拟模型还是被路由到的物理模型。若宿主报物理模型，这段会**永远不生效**且无任何提示（静默跳过网关兼容）。
- `failedTextOf`（`index.ts:23-33`）**会把正常回答文本当错误**：`errorMessage` 缺失时它会拼接 `content` 里所有文本，然后交给 `NON_TRANSIENT` 子串匹配（`decide.ts:136`）。流中断时的半截回答里出现 `401`、`403`、`权限`、`余额`、`额度` 任一子串，就会返回 `NOT_RETRYABLE`，**放弃换链**。这直接违反 04「普通回答中出现 401、503 或余额等字样一概不作为故障」（`plans/v4/04-Pi模型恢复插件.md:54`）。
- `request.state === undefined`：`parseState(undefined)` → 空状态（`index.ts:139`），不崩、不猜索引，**单次 retry 行为正确**（从 failed 的后一个模型起选）。风险在跨请求：本次把模块级 `current` 去掉后，`attempted`/`activeIndex`/`cooldownUntil` 完全依赖宿主回传 `state`。宿主若不回传或跨轮不保留：① 连续 retry 会在两个模型之间来回（`attempted` 每次重置）；② 每次用户新输入都回主模型，冷却形同不存在——正是“每条消息先打一次坏模型”。这一点没有任何探针覆盖（现有 retry 探针只验证了一次 a→b）。
- 另外：`NOT_RETRYABLE` 在 `index.ts:147` 被映射成 `CHAIN_EXHAUSTED`（“配置链已用尽”），用户会得到误导性的结束原因。

### 5. `scripts/package-v4.sh` —— **入口与过滤这两条修对了，摘要实现可移植，仍有小漏**

- manifest 入口：`package-v4.sh:96-97` 写 `SKILL.md` / `index.ts`，与包内实际布局一致；`test-package-v4.sh:32-33` 还断言了文件存在。实测 `package test: passed`。成立。
- 摘要：`package-v4.sh:39-47` 改用 `python3` + `hashlib`，不再依赖 macOS `shasum`；`check-repo.sh` 本来就强制 `python3`，可移植性可接受。注意文件名含换行仍会破，但当前文件集没有。
- `.env` 过滤：`(^|/)\.env` **能**命中 `.env.local`（前缀匹配），`.pem`/`.key` 也已补。仍漏：`.netrc`、`.npmrc`、`id_rsa*`、`*.p12`、`cookies.json`、`credentials.local` 一类；`list_files`（`package-v4.sh:31`）还会**静默丢弃 `*.log`**，等于这类文件永远不会被 `assert_clean` 看见。
- 未修（第一轮已提、不在本轮范围）：`[[ -e "$DEST" ]]`（`package-v4.sh:19`）不识别悬空软链。

### 6. `install.sh` 与 `test-install-v3.sh` —— **清单与断言互相自洽，但断言证明不了“装上能跑”；且存在明显假通过**

- 清单一致：`install.sh:29-30,38-41` 的 `EXT_ENTRY=x-run-guard.ts`、`EXT_FILES` 含 `host-events.ts`，与 `test-install-v3.sh:18-22` 的断言一一对应。`test-install-v3.sh` 实测 `passed`。
- **但装出来的守卫找不到 `xr`，会静默不启用**（本轮最严重的可交付问题）：
  - `run-files.ts:190-200` 的候选只有：`X_RAIL_XR`、`<扩展目录>/../scripts/xr`、`<项目 cwd>/skills/x-rail/scripts/xr`。安装形态是“扩展复制到 `~/.pi/agent/extensions/x-rail/`、技能软链到 `~/.pi/agent/skills/x-rail`”，三个候选都不成立（实测：临时 HOME 下没有 `extensions/scripts/xr`，也没有任何 `xr` 文件）。
  - 后果：`bindRun` 失败 → `session_start` 只报一句 warning（`x-run-guard.ts:85`）→ `bound=null` → `guardBoundary` 第一行就 return。**守卫完全不工作，但 `test-install-v3.sh` 全绿。**
  - 这正是“测试通过但实际装不出守卫”。回归来源可查：`git show 2452416^:skills/x-rail/extensions/run-files.ts` 里第三候选是 `~/.pi/agent/skills/x-rail/scripts/xr`（安装后确实存在），v4 重构用 `import.meta.url` 替换时把它删了。所有探针都靠 `test-run-lifecycle.mjs:215` 的 `env.X_RAIL_XR = xr` 绕过了这个缺口。
- 断言假通过：`test-install-v3.sh:16` 与 `simulate-v4.mjs` 的 `assert.equal(existsSync(x-failover.ts), false)` 在**全新临时 HOME** 上恒真。实测在临时 HOME 先放一个旧 `x-failover.ts` 再跑 `install.sh`，文件**原地保留**（`install.sh` 只按 `EXT_FILES` 增量复制，从不清理旧入口）。升级真实 v3 宿主时，若 Pi 按目录加载（`install.sh:27` 注释自称“pi 会把 extensions/ 下每个 .ts 都当扩展加载”），会出现两个入口都注册 `agent_before_settle`，与“单一入口”的说法直接矛盾；若 Pi 只按 `package.json` 加载，则 `package.json` 这条加载路径本身**从未被任何探针验证**（宿主探针全部用 `--extension <file>` 显式加载）。两种可能都说明测试没覆盖真实安装形态。

---

## 阻塞项（5 条）

### B1. 安装后的守卫解析不到 `xr`，静默变成空转；安装测试只断言文件存在

- `skills/x-rail/extensions/run-files.ts:190-200`（候选缺 `~/.pi/agent/skills/x-rail/scripts/xr`，`2452416` 时被删）
- `skills/x-rail/install.sh:38-41`（不安装/不指向 `xr`，也不设 `X_RAIL_XR`）
- `scripts/test-install-v3.sh:17-19`、`scripts/simulate-v4.mjs:259-266`（只 `existsSync`，不验证可解析）
- 证据：临时 HOME 安装后 `find` 不到任何 `xr`；三个候选路径均不存在。
- 修法（择一）：把 home 候选加回；或安装时把 `scripts/xr`（及其依赖模块）拷进 `extensions/x-rail/` 并让候选指向它；并在 `simulate-v4.mjs` 里用安装后的目录实际跑一次 `bind`。

### B2. `session:` 验收来源仍可伪造定位：不校验 `#entry:`、不要求报告与单元对应

- `skills/x-rail/scripts/xr:1390-1410`，消费点 `xr:1693`
- 证据（/tmp 实测）：run 内有一条针对单元 `r` 的合法 review 证据，另建 `acceptance set A1 ... --source "session:R1#entry:THIS-DOES-NOT-EXIST" --units i`（`i` 与 `r` 无关），`covered=1`。
- 对照 `plans/v4/03-x-rail任务闭环.md:40`。
- 修法：至少要求 `#entry:` 在保存的会话副本里可定位（消息索引/哈希），并要求该 review 证据的单元属于该验收行的 `units`；或引入显式 `来源待核实` 状态，禁止计入 `covered`。

### B3. `session_before_compact` 不覆盖了，但 `agent_before_settle` 仍用“只有胶囊”的 compaction 覆盖上下文；胶囊刷新还可能一直失败

- `skills/x-rail/extensions/x-run-guard.ts:237-239`（`compactText(capsule, null)`）
- `skills/x-rail/extensions/x-run-guard.ts:220`（丢弃 `refreshCapsule` 返回值）
- `skills/x-rail/extensions/run-files.ts:202-212`（`xr capsule` 不带 session，`check_writer` 必拒）
- 修法：删掉这条 `{type:"compaction"}` draft（胶囊只作 `custom_message`/路径提示）；`refreshCapsule` 传 `--session`/`--generation` 或在失败时明确降级为“只附路径”。

### B4. `failedTextOf` 用 assistant `content` 做非暂时错误匹配，会把正常回答当鉴权/余额/权限错误，静默放弃换链

- `plugins/pi-model-recovery/index.ts:23-33`、`:142`；匹配逻辑 `plugins/pi-model-recovery/decide.ts:136`（`NON_TRANSIENT`，含 `401`/`403`/`权限`/`余额` 等短子串）
- 对照 `plans/v4/04-Pi模型恢复插件.md:54`「普通回答中出现 401、503 或余额等字样一概不作为故障」。
- 修法：只用结构化错误字段（`errorMessage` 或宿主 error 对象）；确实需要 content 时要求整段匹配错误形态（如 `^\d{3}:`），并对 `401` 这类数字要求词边界。

### B5. 同会话内 `xr resume` / `xr bind` 让守卫永久停摆（generation 合法递增被判 stale）

- `skills/x-rail/extensions/x-run-guard.ts:178-182`（判 stale 后 `bound = null`，无重绑路径）
- `skills/x-rail/scripts/xr:1937`（`resume` 无条件 `generation += 1`）、`xr:1967`（`bind` 同会话也 +1）
- 后果：用户按设计“暂停→resume”后，守卫只报一条 warning 就退出，之后本进程内不再续跑/记账，只能重启 Pi。方向是“安全停”，但属静默停摆且无恢复入口。
- 修法：`session_id` 相同而 generation 变化时视为“同一会话被合法提升”，就地更新 `bound.generation`；仅 `session_id` 不同才判 stale。`bind` 对同一会话不要递增 generation。

---

## 非阻塞建议（8 条）

1. `skills/x-rail/extensions/x-run-guard.ts:196`：finish 失败提示“请看 handoff”，但该分支不写 handoff；改成 `stopWithHandoff(...)` 或改文案。
2. `skills/x-rail/extensions/x-run-guard.ts:191-198` + `skills/x-rail/scripts/xr:1868-1876`：`done_met`/`onlyReceipt` 在 `lease=paused`、`phase=paused` 时也会 `finish` 并改 phase；且每次 settle 都重写收据并 `epoch+1`。建议 `finish` 加 phase/lease 前置，守卫只在 `automation_allowed` 时收口。
3. `plugins/pi-model-recovery/index.ts:147`：`NOT_RETRYABLE` 被映射成 `CHAIN_EXHAUSTED`，用户看到“配置链已用尽”；应原样抛 `NOT_RETRYABLE`。
4. `plugins/pi-model-recovery/index.ts:138-139`：去掉模块级 `current` 后，多轮 retry / 跨轮冷却完全依赖宿主回传 `state`，无探针覆盖。建议加“宿主不回传 state 时 retry 不得绕回已失败模型”的探针或保守兜底。
5. `plugins/pi-model-recovery/index.ts:166-167`：`ctx.model` 在失败轮到底报虚拟模型还是物理模型，未验证；若是物理模型，网关标记永远不生效（静默跳过）。
6. `skills/x-rail/extensions/x-run-guard.ts:278`：`stopWithHandoff` 仍用 `writeAtomic` 直接写 `handoff.md`，沿用第一轮 Standards 硬违规（绕过运行锁 / 无 generation 校验），两条“扩展不写运行目录状态”的说法不一致。
7. `skills/x-rail/scripts/xr:1390-1410`：`session_hash` 只判非空，不比对文件摘要（篡改 `notes/review-session-*.jsonl` 不影响来源判定）；且每个验收行都重读整张 `ledger.tsv`（O(acc×ledger)），建议一次读出后传入。
8. `scripts/package-v4.sh:19,31,52`：悬空软链 `[[ -e ]]` 不命中；`*.log` 被 `list_files` 静默丢弃；凭据模式仍漏 `.netrc/.npmrc/id_rsa*/*.p12`。另：`test-xr.py` 40 项（commit 与 05 里仍写 39）、`decide.test.ts` 34 项（05 写 31），计数已漂移。

---

## 第一轮 5 条的复核结论

| 第一轮阻塞 | 现状 | 判定 |
| --- | --- | --- |
| `session:` 来源只看格式 | 需要 `notes/` 副本 + `observer`，但 entry/单元不校验 | **部分修复**（B2） |
| 被接管后旧会话仍可续跑 | `inspect.binding` 比对 + `stale-binding` | **成立**，但对同会话合法提代会误伤（B5） |
| 压缩用胶囊覆盖 Pi 摘要 | `session_before_compact` 已不返回 compaction | **部分修复**：`before_settle` 仍有同型写法（B3） |
| 扩展直接写运行目录状态 | `guard.json` 改走 `xr guard set`（锁 + session/generation），失败即停 | **成立**（`handoff.md` 仍直写，见建议 6） |
| 导出包 manifest 指向被排除的 failover | 入口改 `SKILL.md`/`index.ts`，测试断言存在 | **成立** |

对比：上一轮报告里“打包目录不存在的入口”与“Linux 无 `shasum`”两条确实已修；`install.sh` 的清单也对齐了，但“装完可用”这层仍然没有被任何测试覆盖。

## 已确认成立、无需再动的部分（抽样）

- `xr guard set` 在运行锁内写、带 session/generation 校验（`xr:1784-1806` + `run_lock`/`check_writer`）；写失败 `stopWithHandoff`。
- `cmd_finish` 的 `receipt:` 白名单不会放过别的问题（reasons 前缀不可伪造：单元/验收 id 不允许 `:`）。
- `package-v4.sh` 导出拒绝已存在目录、两清单互斥、`test-package-v4.sh` 断言入口文件存在。
- `markGatewayError` 本身仍只附加标记、幂等、不删原文；鉴权/余额/权限不在 `GATEWAY_PATTERNS` 内。
- `xr` 的 `inspect --json` 仍是唯一完成判据，扩展对 schema/字段做了白名单校验（`validInspectSnapshot`）。
