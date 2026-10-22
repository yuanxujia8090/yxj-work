# v4 使用场景测试用例（真实会话回放版）

日期：2026-10-22。取样窗口：2026-10-08 至 2026-10-22。对象：`.worktrees/v4`（分支 `v4`）。

用途：把过去两周真实 Pi 会话里**实际发生过**的 x-rail 用法与卡点，转成可重复执行的 v4 测试用例。每条用例都写清来源、v4 判定和不能声称的边界，避免“测试全绿 = 能替代真实使用”。

## 0. 取样口径

只读扫描本机 `~/.pi/agent/sessions`（不复制日志进仓库）：

| 口径 | 数量 |
| --- | --- |
| 窗口内会话文件（jsonl） | 976 |
| 提到 `x-rail` 的文件 | 432（多数只是技能列表注入，不算使用） |
| 出现技能调用、`.work-docs/tasks` 或 `task.py` 实调的主会话 | 46 |
| `task.py` 的 bash 实调次数 | 148（run / check / update / finish / start / seal / record / summary / capture / complete 等） |
| 非零退出 | 3（另有若干次报错但被同一命令链后段纠正） |
| `xr`（v3/v4 run 命令）实调 | 21 次，集中在 2026-10-19、10-22 |

场景来源以任务 ID 为准（`<任务目录>` 指对应仓库 `.work-docs/tasks/<任务 ID>`，日志原文留在本机会话目录）：

| 场景组 | 代表任务 |
| --- | --- |
| 长任务分阶段 + 跨会话恢复 | website `20261015-04-domain-change-foundation`、`20261015-05/06` |
| 子代理委派 | website `20261016-03-default-platform-free-domain`；x-rail `20261016-01-v006-active-delegation` |
| 只读审查 | website `20261012-07-main-develop-review`、`20261013-03-branch-diff-review`、`20261019-01-cr-1018-text-otlume` |
| bugfix / 缺陷修复 | website `20261016-05-cn01-cn06-defect-fix`、`20261017-01-fix-release-migrate-gate` |
| 发布与运维门禁 | website `20261015-01-email-management-and-free-site-ops` |
| 研究与可行性 | saber-gril `20261012-01-vtuber-local-feasibility`；website `20261009-01-browser-e2e-testing-research` |
| 文档/原型交付 | hermes-work `20261012-01-workbench-prd-html`、`20261012-02-workbench-prototype` |
| worktree 隔离 | x-rail `20261010-05-worktree-skill`；website `2026-10-10 ~ 10-22` 多个 worktree 任务 |
| 记账命令误用纠错 | website `20261015-01`、`20261015-05`、`20261017-01`；x-rail `20261019-01-xr-recovery-readonly-scheduling` |

## 1. 用例总表

判定列写 v4 应满足的可观察行为；“自动入口”写仓库内能跑的命令，没有的写“手工/模型层”。

| 编号 | 场景 | 判定（v4） | 自动入口 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | 单单元 bugfix 从开工到收口 | `init → plan add → next → verify → done → inspect/finish` 全链路可走通；`finish` 生成收据 | `test-xr.py`、`simulate-v4.mjs` | 通过 |
| TC-02 | 多单元有依赖的执行 | 前置当前证据通过才放行后继；前置过期挡住后继，独立分支照常 | `test-xr.py::test_dependency_*`、`test_transitive_stale_dependency_blocks_descendant` | 通过 |
| TC-03 | 文档/原型交付不伪造命令证据 | `--verify-kind observation` + `evidence record --kind observation` 可满足验收 | `test-xr.py::test_human_evidence_scopes_immutable_reports_and_independent_review` | 通过 |
| TC-04 | 只读分支审查 | 审查证据必须来自另一会话的 jsonl，且报告文字出现在其输出里；自审不通过 | `test-xr.py::test_review_evidence_must_come_from_reviewer_output`、`test_review_required_blocks_finish_without_independent_review` | 通过 |
| TC-05 | 交付变更后收口 | 产物/输入一变，旧 VERIFIED 与收据 stale；重取证只追加不覆盖；`finish` 可刷新 | `test-xr.py::test_finish_refuses_stale_evidence`、`test_stale_receipt_can_be_refreshed_by_finish`、`test_tampered_verification_report_cannot_finish` | 通过 |
| TC-06 | 工具副作用结果未知 | 未决工具动作阻止 `verify/done/finish`，守卫只暂停不续跑 | `test-xr.py::test_unknown_tool_blocks_claim_and_done`、宿主探针 | 通过 |
| TC-07 | 子代理启动未终结 / 重复通知 | 未终结不完成且占范围；终态只接收一次 | `test-xr.py::test_worker_receipt_needs_terminal_identity_and_is_idempotent`、宿主探针 | 通过 |
| TC-08 | 换会话继续同一任务 | 旧会话写入被拒（退出 2 并给正确命令）；接管需 `resume --take-ownership` 并递增 generation | `test-xr.py::test_takeover_advances_generation_and_rejects_stale_writer` | 通过 |
| TC-09 | 用户中断 | 真实 RPC abort 后续跑次数 0，不伪造 error | `test-run-lifecycle.mjs`（`real abort`） | 通过 |
| TC-10 | 长时间无进展 | 连续 3 次语义进度不变即停并写 `handoff.md`；重开会话计数不归零 | `test-run-lifecycle.mjs`、`test-installed-layout.mjs` | 通过 |
| TC-11 | 跨 worktree / 跨目录隔离 | run 只在所属工作区可见；别的目录 `inspect` 退出 2，不串用 ACTIVE | 本次新增手工探针（见 §2 TC-11） | 通过 |
| TC-12 | 并发初始化 | 同仓库两进程竞争只留一个 ACTIVE，另一个被拒 | `test-xr.py::test_concurrent_init_preserves_single_owner` | 通过 |
| TC-13 | 把 v3 命令照抄到 v4 | 拒绝并给出可理解提示，不能静默写错结构 | 本次新增手工探针（见 §2 TC-13） | 部分通过（提示不够具体） |
| TC-14 | 单单元任务直接收口 | `inspect` 说明缺什么 | 本次新增手工探针（见 §2 TC-14） | **不通过（文档缺口）** |
| TC-15 | 装了守卫但没装模型插件 | 任务层照常；模型行为回到 Pi 原生，不自动换模型 | `test-model-recovery.mjs`、`typecheck-extensions.sh` | 通过 |
| TC-16 | 安装到临时 HOME 后实际跑一轮 | 守卫能找到 `<agent-dir>/skills/x-rail/scripts/xr` 并续跑 | `test-installed-layout.mjs` | 通过 |
| TC-17 | 无 run 的普通会话 | 不开 `.work-docs/runs`、不调 xr、不发额外请求 | `test-run-lifecycle.mjs` | 通过 |

## 2. 用例明细

### TC-01 单单元 bugfix 收口

来源：website `20261016-05-cn01-cn06-defect-fix`、`20261017-01-fix-release-migrate-gate`（当次走 v3 的 `task.py start/check/seal/complete`）。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-xr.py
node scripts/simulate-v4.mjs
```

判定：命令退出 0，且测试计数明确（41 项、20 项）。只说明记录规则成立，不代表真实模型会自觉收口。

### TC-02 多单元依赖

来源：website `20261015-04-domain-change-foundation`（基础改动 → 确认 → API 三段拆任务）。

判定：改前置输入后 `inspect` 拒绝前置，后继不可启动，旁支可启动。证据：`test-xr.py` 中 `test_dependency_requires_current_verification_evidence`、`test_transitive_stale_dependency_blocks_descendant`。

### TC-03 文档/原型交付

来源：hermes-work `20261012-01-workbench-prd-html`、`20261012-02-workbench-prototype`（当时没有可执行验证命令）。

```bash
xr plan add d1 "PRD 结构完整" --deps none --files docs/prd.md --verify-kind observation
xr evidence record d1 --kind observation --report docs/prd-review.md --record <来源>
```

判定：观察证据进入同一 `ledger.tsv`（`verify_kind=observation`），报告必须非空且在仓库内，不可覆盖旧报告。

### TC-04 只读审查

来源：website `20261012-07-main-develop-review`、`20261013-03-branch-diff-review`、`20261019-01-cr-1018-text-otlume`（用户明确“只审查不修改”）。

判定：审查证据绑定的会话 jsonl 必须是另一个会话、cwd 是当前仓库、报告文字出现在它的助手输出里；`review_required: true` 时无有效审查不能 `finish`。

边界：不能断言“模型一定会另开会话审查”，只能断言“自审被程序拒绝”。

### TC-05 交付变更后收口

来源：website `20261017-01-fix-release-migrate-gate`（审查后改代码，旧证据需重取）。

判定：改文件后 `inspect` 把单元标 stale、收据 stale；重跑 `verify` 只追加新 attempt；`finish` 刷新收据后 `done_met=true`。

### TC-06 / TC-07 工具副作用与子代理

来源：website `20261016-03-default-platform-free-domain`（“任务尽量交给子agent执行”）、x-rail `20261016-01-v006-active-delegation`；历史失败矩阵见 `plans/v4/evidence/subagent-session-scenarios-2026-10.md`。

```bash
HOST_PROBE_PI=/Users/yuanxj/.hermes/node/bin/pi TMPDIR=/tmp/xrail-probe node scripts/test-run-lifecycle.mjs
python3 scripts/test-subagent-scenarios.py
```

判定：意图先于执行、成功/报错/被阻断各自配对；未终结的子任务不进完成门；重复通知只落一次。

边界：宿主进程被杀、网络中断等“最后一条事件丢失”不在本轮证明范围。

### TC-08 / TC-09 / TC-10 换会话、中断、无进展

来源：website `20261015-04 → 20261015-05/06`（用户直接贴 `handoff.md` 继续下个任务）；本机会话里多次出现“继续下个任务”“完成后提交代码”。

手工探针（本次执行，2026-10-22）：

```bash
env -u PI_SESSION_ID XR_SESSION=s1 xr init one        # ok
env -u PI_SESSION_ID XR_SESSION=s2 xr next            # xr: session 与当前绑定不一致，拒绝旧会话写入（rc=2）
env -u PI_SESSION_ID XR_SESSION=s2 xr bind --session s2
#   xr: 该运行被另一会话占用：s1。正确命令：xr resume --confirm --take-ownership --record <依据>（rc=2）
```

判定：旧会话不能写；接管需要显式确认。中断与无进展由宿主探针覆盖（abort 后续跑 0；连续 3 次无进展停）。

### TC-11 跨 worktree 隔离

来源：x-rail `20261010-05-worktree-skill`，以及本周 website 全部工作都在 `.worktrees/*` 下进行（`1008-design-vip`、`1010-prod-fix`、`1017-deploy-fix`、`1018-fix-text`、`1022-user-template`）。

手工探针：`git worktree` 建两个工作区，A 里 `xr init`，在 B（主仓库）执行 `xr inspect`：

```text
xr: 没有 active run。正确命令：xr init <slug>     # rc=2
```

判定：run 落在 A 的 `.work-docs/runs`，B 看不到也不复用 —— 隔离成立。

### TC-12 并发初始化

来源：website 同一时段多个 worktree 并行任务，存在同时起 run 的现实条件。

判定：`test_concurrent_init_preserves_single_owner` 通过（两进程只留一个 ACTIVE）。

### TC-13 把 v3 命令照抄到 v4

来源（真实发生过，全部在 v3 的 `task.py`）：

| 任务 | 当时报错 |
| --- | --- |
| website `20261015-01-email-management-and-free-site-ops` | `task.py record: error: argument --review: not allowed with argument --acceptance` |
| website `20261015-05-domain-change-confirm` | `task.py run: error: the following arguments are required: --expect` |
| website `20261017-01-fix-release-migrate-gate` | `task.py record: error: argument --acceptance: not allowed with …` |
| x-rail `20261019-01-xr-recovery-readonly-scheduling` | `task: input summary cannot include task state or evidence`；`task: report must be a non-empty observation artifact, not task state or contract` |

v4 实测：

```bash
xr evidence record u2 --kind observation --report README.md --record README.md --acceptance A1 --review
# xr: error: unrecognized arguments: --acceptance A1 --review
# xr: 参数不对。正确命令：xr init <slug> | xr plan add … | xr next | xr verify <id> | xr done <id> | …
```

判定：拒绝正确（退出 2），但“正确命令”清单没有 `evidence record` 与 `acceptance set` 的形状 —— 照抄 v3 的用户拿不到该用的那条命令。**部分通过**。

### TC-14 单单元任务直接收口

来源：对应本周最常见的形态（一个 bugfix、一个文档、一次审查），v3 用 `task.py complete` 一步收口。

v4 实测（单单元 + 已 `done`）：

```text
inspect --json → done_met=false, reasons=['u2 verifying', '验收表为空', '缺少最终集成单元']
然后：xr plan add i1 … --kind integration → next → verify → done
再：xr acceptance set A1 "…" --source README.md --units i1
inspect → done_met=true, reasons=[]
xr finish → ok 20261022-2300-one（写出 finish.json，含验收/单元/账本/树摘要）
```

判定：机制本身正确（集成单元 + 验收表是完成的必要条件），但 `skills/x-rail/stages/*.md` 与 `SKILL.md` 都没有写这两步，`land.md` 也只说“run 可以停下”，不提 `xr finish`。**按文档操作会在收口处停住 → 不通过（文档缺口）**。

### TC-15 ~ TC-17 安装与隔离

```bash
node plugins/pi-model-recovery/decide.test.ts     # 35 项
node scripts/test-model-recovery.mjs              # 6 项，3 次本地请求
bash scripts/typecheck-extensions.sh
HOST_PROBE_PI=/Users/yuanxj/.hermes/node/bin/pi node scripts/test-installed-layout.mjs   # 8 项
```

判定：不选虚拟模型的会话零影响；装到临时 HOME 后守卫能经安装布局调用 `xr` 续跑；无 run 的普通会话不建 `.work-docs/runs`。

## 3. 执行记录

见 `plans/v4/evidence/v4-usage-test-run-20261022.md`（命令与原始输出摘要）。汇总：

| 用例 | 结果 |
| --- | --- |
| TC-01/02/03/04/05/06/07/08/12/17 | 通过 |
| TC-09/10/15/16 | 通过 |
| TC-11 | 通过（本次探针） |
| TC-13 | 部分通过（提示缺具体命令） |
| TC-14 | 不通过（阶段卡/入口未写集成单元、验收表、`xr finish`） |

## 4. 测试发现（按影响排序）

1. **阶段卡与入口没写收口三步**：`xr plan add … --kind integration`、`xr acceptance set`、`xr finish`。代码要求前两者齐备才 `done_met=true`，而文档只写到 `xr done` 与 `xr status`。按文档执行的真实用户会在收口处看到 `done_met=false` 且没有下一步线索。
2. **`finish` 失败提示太泛**：实际输出“补齐验收和集成验证后重试”，没给命令形状；v3 的同类提示都带 `正确命令：`。
3. **`plans/v4/03-x-rail任务闭环.md` 与代码冲突**：文档说最终 integration 单元“也可组合命令与观察证据”（读作可选），代码把它列为完成的硬条件。
4. **`XR_SESSION` 在 Pi 会话里形同虚设**：宿主总是设置 `PI_SESSION_ID`，且优先级更高，所以导出 `XR_SESSION` 不生效。离线/手工要绑定必须 `--offline` 或 `--session`。文档只写“识别 PI_SESSION_ID/XR_SESSION”，没写优先级。

## 5. 覆盖边界（不得据此声称）

- 模型是否自觉遵守提示（路由、只读、不伪造证据）：本轮只验证程序会拒绝，不验证模型不犯错。
- 真实网关错误分类、余额/鉴权分支的真实宿主行为：未验证。
- 工具副作用“恰好一次”、200 次续跑上限、压缩摘要实际路径、`worker_started` 是否可被模型伪造：未验证。
- 本文件中的“通过”只代表对应命令的当前输出；换机器、换 Pi 版本需重跑。
