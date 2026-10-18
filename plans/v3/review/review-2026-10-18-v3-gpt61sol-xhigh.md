# x-rail v3 中文代码审查报告

- 日期：2026-10-18
- 审查标识：gpt-6.1-sol / xhigh
- 当前分支：`v3`
- HEAD：`4ccfd3a7d4d4489c972636a6aaef12dbabcd759`（`fix(x-rail): close v3 reliability gaps`）
- 主审基准：`d6fc6a1`（已解析为 `d6fc6a101e720cf7f112151f202f5a587acfec14`）
- 附加比较基准：`main` 的合并基点 `b158f20`
- 主审范围：`git diff d6fc6a1...HEAD`
- 主审范围事实：基准有效，diff 非空；涉及 27 个文件，约 `+2982/-379`。
- 附加范围：整个 `v3` 分支相对 `main` 的风险区域，重点覆盖扩展、`skills/x-rail/scripts/`、安装脚本、文档和测试。

## 概览

本次改动把扩展入口合并、引入持久化锁和原子写入、补上 `revise` 及并发测试，且 Python/TypeScript/安装相关测试的正常路径均有覆盖。主要风险集中在“验证命令的进程树隔离”和“扩展在关键状态变化时仍使用过期快照”两处：前者会让超时后的后台子进程继续修改工作区，后者会在并发 failover / 工具结果期间丢失一部分持久化状态。另有若干规格缺口：扩展仍未实现文档要求的摘要模型超时降级和实际探活，`xr` 的跨平台、空 scope 和导入校验不足。

结论不是“不能合并”，但建议先处理 P1，再把规格中仍标为“待确认”的宿主行为明确标成未验证，不要把现有单元测试绿色等同于真实 Pi 回放验收。

### 按轴统计

| 审查轴 | P0 | P1 | P2 | 合计 |
|---|---:|---:|---:|---:|
| Standards | 0 | 2 | 2 | 4 |
| Spec | 0 | 3 | 3 | 6 |
| 附加：整分支风险区域 | 0 | 1 | 2 | 3 |

> 严重级别含义：P0 是会造成严重数据/安全/完成性事故且应立即阻断；P1 是常规路径会造成错误结果、失真证据或可靠性失效；P2 是边界条件、可维护性或覆盖不足，需修但不必立即阻断。

## Standards 轴

### P1-S1：验证超时只杀 shell 进程组，脱离的后台子进程仍可继续改工作区

- 严重级别：P1
- 编号：P1-S1
- 文件行号：`skills/x-rail/scripts/task.py:542-550`
- 证据：验证命令通过 `/bin/bash -o pipefail -c ...` 以新会话启动；超时后调用 `os.killpg(process.pid, signal.SIGKILL)`，随后只等待该 shell。一个实际复现中，命令启动 `sleep 2; touch late.txt` 的后台子进程并等待 5 秒，`task.py run --timeout 1` 已返回失败，但 3 秒后 `late.txt` 仍出现。
- 影响：命令已经被记为失败，调用方可能马上修改代码、重新验证或宣称工作区稳定；旧验证的后台进程随后可以覆盖文件，造成竞态、污染后续 tree hash，并让“验证期间工作区未变化”的保护失效。对于带后台服务、脱离终端的测试脚本尤其危险。
- 修复建议：不要只依赖 shell 进程组；优先使用能保证全体后代被终止的执行器/进程树管理，超时后确认进程组和后代均已退出，再写入失败证据。验证命令应在隔离工作目录执行，或禁止/审计后台脱离行为。补一条回归测试：后台子进程在超时后尝试修改 scope，必须在 `run` 返回前被阻止。

### P1-S2：原子写入实现没有保证父目录落盘，断电后可能丢失已替换文件

- 严重级别：P1
- 编号：P1-S2
- 文件行号：`skills/x-rail/extensions/file-io.ts:3-12`；同类实现：`skills/x-rail/scripts/xr:82-95`、`skills/x-rail/scripts/task.py:132-142`
- 证据：文件内容写入并 `fsync` 后直接 `rename`/`os.replace`，没有对父目录执行 `fsync`。这些函数被用于熔断器状态、run 状态、胶囊和 ledger 等恢复关键文件。
- 影响：在主机断电或文件系统崩溃窗口内，文件内容可能已经写入但目录项更新未持久化，恢复后看到旧版本或临时文件；熔断状态、续跑次数和验证 ledger 可能退回，进而重复派发、重复切换模型或丢失完成证据。常规进程测试不会暴露这个问题，但“持久化检查点”语义不完整。
- 修复建议：在同一目录创建临时文件、写入并同步后替换，再打开父目录并 `fsync`；临时文件和目标文件的权限、目录创建也要纳入失败处理。对不承诺断电持久性的文件明确降级，不把它们称为可靠检查点。

### P2-S1：`xr` 直接拼接 TSV 字段，空白和合法范围校验分散，容易产生难诊断的记录坏味道

- 严重级别：P2
- 编号：P2-S1
- 文件行号：`skills/x-rail/scripts/xr:98-102`、`385-429`
- 证据：`write_tsv` 只调用 `cell` 检查制表符和换行；`plan add` 对 `--files` 先做 `check_scope`，但写入的是原始 `args.files`；`--deps` 仅清理逗号分隔项，没有统一检查每个依赖标识。后续读取依赖时 `ready` 使用“只对已知依赖取值”的逻辑，未知依赖会被静默跳过并可能把单元视为 ready。
- 影响：用户传入带空格的文件集、重复分隔项或未知依赖时，状态文件仍可生成；后续调度结果可能与用户看到的计划不一致。错误没有在入口处 fail closed，增加恢复成本。
- 修复建议：在 `plan add` 中保存规范化后的 scope，严格校验依赖 ID、空项、重复项和所有依赖存在性；`ready` 对未知依赖直接报错而不是跳过。将 TSV 行和领域字段封装成明确类型/校验函数，避免 primitive obsession（用普通字符串承载计划单元、scope 和依赖语义）。

### P2-S2：单文件/单模块同时承担多种生命周期职责，测试没有覆盖职责间的事件顺序

- 严重级别：P2
- 编号：P2-S2
- 文件行号：`skills/x-rail/extensions/x-failover.ts:30-202`、`skills/x-rail/extensions/x-run-guard.ts:29-125`
- 证据：`x-failover.ts` 同时注册 failover、failback、命令、工具计数、看门狗回调和 run guard；`agent_before_settle` 先处理切回，再分类故障、写状态、调用 guard。现有 `failover.test.ts` 主要覆盖纯函数，没有模拟多个生命周期处理器并发/重入、`setModel` 失败后 guard 是否继续、或 `session_before_compact` 与自定义 compaction entry 的顺序。
- 影响：一个事件顺序变化即可让切回、续跑和看门狗互相覆盖；问题会表现为偶发重复续跑、漏写事件或状态错配，难以从纯函数测试定位。
- 修复建议：保留单一入口的宿主注册设计，但把事件处理拆成可测试的协调器；为 `agent_before_settle` 建立顺序测试矩阵（正常完成、E3、E2 重试、看门狗、切回、setModel 失败、压缩），并显式定义每一步的持久化边界。

## Spec 轴

### P1-P1：验证超时后的后台副作用违背“失败后可安全恢复、验证边界可信”的规格

- 严重级别：P1
- 编号：P1-P1
- 文件行号：`skills/x-rail/scripts/task.py:542-551`
- 证据：`plans/v3/03-技术方案.md:144-146`要求超时按 cap-hit 处理并重新派发；`plans/v3/03-技术方案.md:186-190`要求每个验证写入当前 tree 的证据且最终 tree 上验证通过。实现只杀直接 shell 进程组，实际后台子进程在 `run` 返回后仍能修改工作区。
- 影响：重新派发或后续 `xr verify` 可能与旧命令同时写文件；验证返回失败时，工作区仍处于未定义的变化状态，无法把失败 ledger 当作一个稳定的时间点。这样会破坏“超时后缩小范围再派发”和“当前 tree 证据”的前提。
- 修复建议：采用进程树收敛和返回前确认；失败证据要记录被终止的进程清单/是否仍有后代；必要时隔离验证工作区并在结束后重新计算受影响 scope。

### P1-P2：看门狗标记没有接入故障分类，E5 规格在真实生命周期中不会按 E3 处理

- 严重级别：P1
- 编号：P1-P2
- 文件行号：`skills/x-rail/extensions/x-run-guard.ts:59-65`、`skills/x-rail/extensions/x-failover.ts:128-133`
- 证据：`x-run-guard` 在 watchdog 触发后调用 `markWatchdog()` 并 abort；settled 时通过 `takeWatchdog()` 判断并调用回调，但回调只找 bai、`setModel`、`sendMessage`。与此同时，`x-failover.ts` 的正常 `agent_before_settle` 固定传 `watchdog: false`，没有把 watchdog 标记转成 `classifyError(... watchdog: true)`，也没有调用 `decideSwitch` 的 E5 路径。`plans/v3/04-模型降级与续跑.md:28-29`明确要求 E5 按 E3 处理。
- 影响：看门狗触发后不能共享熔断器、failover 次数和事件记录；如果兜底模型不存在或切换失败，直接停止，且不会走统一的 E3 处理和 handoff 逻辑。现有纯函数测试只验证 `watchdogDue` 和 `classifyError({watchdog:true})`，没有验证实际事件链。
- 修复建议：让看门狗回调返回/持久化一个明确的 E5 settle 结果，或在统一的 `agent_before_settle` 中消费一次性标记并传 `watchdog: true`；复用同一套分类、熔断、切换、有限重试和事件记录，不要复制一条旁路切换逻辑。补 Pi 生命周期集成测试。

### P1-P3：failover 状态的读取—计算—写回仍使用旧快照，跨会话更新可能被覆盖

- 严重级别：P1
- 编号：P1-P3
- 文件行号：`skills/x-rail/extensions/x-failover.ts:80-157`
- 证据：`agent_before_settle` 开始先 `const state = loadState(file)`；随后基于该快照计算 breaker、memory 和 failback。虽然最后 `updateState` 会重新加载最新文件，但回调中又以外部旧 `state` 派生 `memory`、`disabled` 和 `breaker` 的决策；同时 `tool_result`、另一个 session 的 settle 和命令都可以在这两个操作之间更新同一文件。最后更新只合并部分字段，且 `latest.runs[id] = memoryAfter(memoryFor(latest,id), decision)`可能用旧 memory 再应用一次决策。
- 影响：并发事件可能丢失工具计数、覆盖较新的 `disabled`/breaker 变化，或把同一故障按旧计数再次计算；故障熔断和“连续无工具进展”上限不再严格。已有 `store.ts` 的锁只保护每次读写回调，不保护整个业务事务。
- 修复建议：把“读取当前状态、计算决策、写入状态”放进一个锁内的单事务，或给状态加版本号并在提交时检测冲突；决策使用事务内的最新 state。工具计数与 settle 事件还要按 run/turn 去重，避免同一宿主事件重复记账。

### P2-P1：`xr` 的规格要求跨平台和空 scope 防护，但实现仍有平台/边界缺口

- 严重级别：P2
- 编号：P2-P1
- 文件行号：`skills/x-rail/scripts/xr:226-254`、`488-526`
- 证据：`plans/v3/03-技术方案.md:78-88`和`plans/v3/03-技术方案.md:209-213`要求 `--files` 作为独占文件集参与冲突检查，且 `xr verify` 以 scope tree hash 作为证据。实现对不存在的普通文件、尚未创建的目录和匹配为空的 glob 直接报错；这会阻止“先规划、后由 worker 创建文件”的正常计划。另一方面，`cmd_verify` 使用 `subprocess.run(..., shell=True)`，超时异常只保存部分 stdout，不保证后台进程终止；`tree_hash` 只对 `repo.glob` 返回的普通路径做有限检查，没有在收集阶段统一拒绝 scope 内部软链，且 `scope_parts` 只用 `PurePosixPath`，在 Windows 上的路径语义与运行命令不一致。
- 影响：计划阶段不能可靠表达尚未存在的实现文件；不同平台上相同 `--files` 可能得到不同 scope；验证超时会继续污染 tree，证据和并发写入隔离失真。
- 修复建议：区分“计划 scope”与“验证时 scope”：允许不存在的明确文件作为计划范围，但在 verify 时要求实际匹配并记录；统一用平台无关的相对路径规范化和软链策略；使用可控进程组/隔离目录执行验证，并为这三类边界加测试。

### P2-P2：failback 实际没有实现规格要求的“连续两次探活成功”

- 严重级别：P2
- 编号：P2-P2
- 文件行号：`skills/x-rail/extensions/x-failover.ts:87-117`、`skills/x-rail/extensions/failback.ts:31-49`
- 证据：`decideFailback`只有在 `probeAvailable` 时才检查 `consecutiveProbeOk < 2`；调用处把 `probeAvailable` 固定为 `process.env.X_FAILOVER_PROBE === "1"`，仓库没有看到实际探活调用，`applyProbe`只是暴露给外部的状态写入口。默认环境下是 `false`，所以冷却结束后在单元边界就可以直接切回。`plans/v3/04-模型降级与续跑.md:80-92`要求冷却期结束后连续成功 2 次探活，若做不到才允许明确退化。
- 影响：主模型可能刚恢复就被切回并再次失败，放大切换抖动；用户无法从当前实现判断探活是否成功，配置项只是环境变量开关而非功能实现。
- 修复建议：实现带超时、结果记录和去重的真实探活，并把探活结果接入持久化状态；在探活不可用时显式采用文档写明的退化策略和事件记录，不要用隐式环境变量绕过条件。

### P2-P3：`x-run-guard` 的边界决策只实现“继续/压缩”，丢失规格中的依赖推理、开新会话和子代理分支

- 严重级别：P2
- 编号：P2-P3
- 文件行号：`skills/x-rail/extensions/guard-core.ts:70-78`、`skills/x-rail/extensions/x-run-guard.ts:107-125`
- 证据：`plans/v3/03-技术方案.md:156-167`定义四路决策：继续、无关时带胶囊开新会话、可无人值守时派子代理、其他情况主动压缩；实现 `boundaryDecision`只按 provider 与 token 数返回 `continue|compact`，并忽略 `pending-boundary.json` 中的 `dependsOnReasoning`、`unrelated`、`unattended`字段。`cmd_done`写入这三个字段，但消费端不使用。
- 影响：每个单元完成后无法按规格隔离无关上下文或自动把独立单元交给子代理；系统会在不该继续时继续携带历史，或在可继续时不必要压缩，长任务成本和上下文风险上升。
- 修复建议：恢复四路决策所需输入和动作接口；若宿主不能新建会话或派发子代理，至少明确记录“能力不可用”的退化，并在文档/验收中把该项标为未实现，不要保留无效字段造成假象。

## 附加：整分支风险区域（相对 `main`）

### P1-A1：安装脚本不是完整事务，复制过程中失败会留下半安装状态

- 严重级别：P1
- 编号：P1-A1
- 文件行号：`skills/x-rail/install.sh:72-108`
- 证据：脚本按技能软链、扩展文件、`package.json`逐项执行；每个文件变化时先 `backup_path` 移走旧目标，再 `cp` 新文件。任一中途 `cp`、源文件检查、权限或磁盘错误触发 `set -e` 后，没有统一回滚。备份目录名称只精确到秒，重复并发安装还可能争用同一个备份目录。现有 `test-install-v3.sh`只验证 dry-run、成功安装、重复安装和一个软链备份场景，没有注入中途失败或并发安装。
- 影响：真实 HOME 可能只安装了部分扩展或部分技能；Pi 下次启动时可能加载不完整版本。用户重新运行时又会把残缺状态继续备份，恢复路径变长。对安装脚本而言，幂等成功不等于失败可恢复。
- 修复建议：先复制到临时目录并完成全部校验，再以目录级原子切换或带 manifest 的事务方式替换；失败时恢复已移动目标。备份名加入纳秒/PID并用独占创建。补“第 N 个文件失败后目标树与安装前一致”的测试。

### P2-A2：`check-repo.sh` 的门禁依赖 `grep`，没有将相关新增测试纳入完整回归

- 严重级别：P2
- 编号：P2-A2
- 文件行号：`scripts/check-repo.sh:75-76`
- 证据：本次在 `check-repo.sh`新增的回归只执行 `scripts/test-xr.py`和`test-install-v3.sh`，没有执行已在分支中的 `test-frontier.py`、`test-coordination.py`、`test-task-checks.py`、`test-failover.sh`或 `typecheck-extensions.sh`。本次独立实际运行这些命令均返回成功，但“仓库门禁覆盖完整回归”仍未成立；新增 27 文件的关键可靠性行为也没有对应端到端生命周期测试。
- 影响：后续开发者只跑官方门禁时，coordination、frontier、task-checks 和 TypeScript 扩展回归可以悄悄退化而不被发现；尤其本报告中发现的 watchdog、并发状态事务和验证超时后代进程问题不会被门禁抓住。
- 修复建议：让 `check-repo.sh`调用统一的测试入口，至少覆盖 Python 全套、扩展类型检查/故障测试和安装测试；为真实 Pi 事件链保留可运行的 mock 生命周期测试，并在输出中明确每组测试。

### P2-A3：文档/规范新增内容存在格式噪声，`git diff --check`不是干净的

- 严重级别：P2
- 编号：P2-A3
- 文件行号：`plans/0.0.7/会话01a149b6中断原因与原分析评估.md:3-5`、`plans/0.0.7/限制条件与中断风险分析.md:3-5`
- 证据：`git diff --check d6fc6a1...HEAD`实际报告 6 处新增 trailing whitespace，均在上述两份新增文档的引用行末尾。它们不是主运行时代码，但会让仓库的差异检查失败，并且与“文档也应可审计、干净提交”的标准不一致。
- 影响：若 CI 或提交钩子执行 `git diff --check`，本分支会直接失败；文档 diff 中的不可见空格也增加后续审查噪声。
- 修复建议：去除这 6 处行尾空格，并把 `git diff --check d6fc6a1...HEAD`纳入正式门禁。

## 总结

### 当前优点

- 已验证基准和范围清晰：`d6fc6a1`、`HEAD`、`main` 合并基点均可解析，主审 diff 非空。
- 状态写入比原实现更稳：`store.ts`新增锁，`file-io.ts`/`xr`/`task.py`引入临时文件替换；`xr next`新增并发测试，扩展入口改为单一 manifest 入口。
- Python 侧证据和协调模型已有较完整的 fail-closed 检查，成功/失败/旧运行/输入变化/软链边界均有测试。
- 本次独立实际运行并通过：`scripts/test-xr.py`（6 项）、`scripts/test-frontier.py`（5 项）、`scripts/test-coordination.py`（11 项）、`scripts/test-task-checks.py`（73 项）、`scripts/test-failover.sh`（TypeScript failover 与 mock26）、`scripts/typecheck-extensions.sh`、`scripts/test-install-v3.sh`、`scripts/check-repo.sh`。

### 需要优先处理

1. 先修 `task.py` 和 `xr` 验证命令的后代进程终止与隔离；这是会直接污染后续工作区和证据的 P1。
2. 再把 `x-failover` 的状态事务合并到锁内，并把 watchdog 统一接入 E5 分类；否则并发和看门狗都绕开了部分可靠性机制。
3. 明确 failback 探活和四路边界决策是“已实现”还是“待宿主能力确认”，补齐真实生命周期 mock；不要用纯函数绿色测试替代 Pi 集成验收。
4. 修安装事务和完整门禁覆盖；最后清理 `git diff --check` 报告的文档行尾空格。

### 未验证/待确认

- Pi 本机版本是否提供并按预期触发 `agent_before_settle`、`agent_settled`、`session_before_compact`、`setModel`、`sendMessage` 等事件/接口。
- `pi-smart-compact` 与本扩展同时挂载压缩事件时的执行顺序。
- 子代理 Pi 进程是否加载全局扩展，以及中途失败时是否能在子代理内部完成 failover。
- 本报告未读取 `plans/v3/review/` 既有报告，也未读取 `~/Desktop` 文件。

### 审查证据与状态

- 工作区在审查前后均保持 `v3...origin/v3 [ahead 1]`，未发现文件变更；本报告是唯一写入文件。
- `git diff --check` 的实际输出为上述 6 处文档 trailing whitespace；其余测试命令的实际退出结果均为 0。
