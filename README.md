# x-rail

独立的工作流技能仓库。源仓库是唯一事实源。安装形态为副本或直达源仓库的软链。

[使用指南](docs/usage-guide.html)介绍阶段和常见场景。[0.0.4 方案](plans/0.0.4/README.md)规定工作项清单、逐项状态和有边界的并行；脚本回归与真实行为演练分别取证。[0.0.3 方案](plans/0.0.3/README.md)规定本地实现与真实行为验证的边界。

## 入口与加载

- `/x-rail`：普通任务，支持快速回答、调查、研究、设计、计划、执行、修复、审查、操作指引和组合任务。
- `/x-rail-long`：跨会话、外部等待或独立依赖汇总；进入长入口后优先使用子代理承接完整执行单元。多个阶段本身不触发长模式。
- `/x-handoff`：用户明确调用时写当前任务交接。
- `/x-self-check`：用户明确调用时只读分析七日或三周记录。

`scripts/runtime-skills.txt` 是安装范围的唯一来源。当前为 4 个入口和 32 个辅助技能。所有技能设 `disable-model-invocation: true`，不会由任务内容自动唤起。主入口 XML 的 routing 模块维护阶段、说明文件和按需参考映射。TypeScript 规则仅在项目规范不足且当前代码使用该语言时读取。调用 `/x-rail` 即授权当前目标范围内默认主动委派完整执行单元；这不代表无限成本、新购买、生产、不可逆、发布或范围变更，用户禁止、更高规则和宿主限制优先。

XML（Extensible Markup Language，可扩展标记语言）像组件标签，只分隔不同职责。它不授予权限。用户只要分析时只在回复交付，不创建任务或目标文件。用户要写文档时只写授权目录。

## 任务分流

先看要交付什么，再决定记录强度：

| 交付目标 | 默认路径 | 默认记录 |
|---|---|---|
| 简单解释或单一事实 | `fast-answer` | 直接回答，不建任务目录 |
| 调查、研究、方案或审查 | `investigate` / `research` / `design` / `review` | 只读任务默认直接交付；需要跨会话或用户明确要求时才建严格记录 |
| 低风险、可逆的小修改或文档 | `bugfix` / `exec` / `plan` | 普通短流程：先读、最小改动、实际验证 |
| 复杂或大范围实施、跨会话、外部等待、必需依赖汇总或敏感动作 | 对应阶段 + 严格记录 | 使用 `contract.md`、`state.md`、证据和完成门 |

普通任务不创建 `contract.md`、`state.md`、封存快照、输入摘要或候选状态。严格任务仍保留完整证据链。任务规模 `L1/L2/L3` 是预算，不等于记录强度；复杂但当前会话可完成的任务不自动进入长模式。已有严格任务必须续接原契约，不得用普通流程降级。

复杂或大范围实施必须先按逻辑独立性、复杂度、范围和依赖拆成可验证工作项，并持久记录。多个独立复杂逻辑、一个跨模块大范围需求，或单需求内权限/并发/多步写入，都不能因需求少免拆。多个局部简单同源改动可合项并说明依据；不按五个、六个数量分流。已有合格计划核对覆盖后复用。只读分析在回复列项、不落盘；仅要方案文档只写授权位置。拆分不自动进入长模式，但不抵消 `/x-rail` 已有的当前目标范围委派授权。

## 安装

需要 Bash 和 Python 3.10 或更新版本。只使用标准库，不新增第三方包。`zoneinfo` 使用系统时区数据。

```bash
bash scripts/check-repo.sh
bash scripts/install.sh --dest <新的隔离目录>
bash scripts/check-workflow.sh --source "$PWD" --installed <隔离目录>
```

复制安装拒绝覆盖。`--update` 会删除并替换已标记目录，需要事先确认风险。软链安装用 `--link`，正确已有链接保持不变；外来链接、断链、目录均拒绝接管。`--unlink` 删除指向本仓库的链接，需要明确清理授权。不要因安装测试就修改 `~/.pi/agent/skills`。

真实全局安装前先检查路径和归属。软链指向主仓库时，隔离分支的改动不会自动生效。

## 任务记录

正式任务在命令实际执行目录下创建 `.work-docs/tasks/<task-id>/`。同范围进行中任务续用编号。编号为 `{YYYYMMDD}-{NN}-{slug}`，日期为创建日，序号当日自增且不回收。工作流记录只写该目录；项目代码和用户授权的项目文档是目标文件，不伪装为记录。

```text
.work-docs/
├── index.md
└── tasks/<task-id>/
    ├── contract.md
    ├── state.md
    ├── handoff.md
    ├── evidence/
    ├── outputs/
    ├── audit/
    └── tmp/
```

契约记录目标、范围、禁止动作、风险、审查策略、版本、Acceptance（编号验收条件）、Decision Gates（授权记录）和变更。每条验收有 outcome、verification、verification_type、layer、required。可选项必须预先写 skip_reason。字段从第一列写 `key: value`，不是 Markdown 列表。

风险决定审查强度。确认只针对不可逆、支出、对外发布、需求范围变化。`action_categories: none` 可以豁免确认，不豁免所需审查；有敏感动作时必须绑定当前动作的用户确认来源。独立审查需要委派授权；未获授权单列阻塞，不能把主会话核对冒充独立审查。

## 严格检查与完成

普通任务不使用下面命令。严格任务从源或安装技能目录调用，不要求消费者项目含 `skills/`：

```bash
# 写好 contract.md 后：生成 state.md、封存契约并校验
python3 <skill-dir>/scripts/task.py start <task-dir>
# 自动验收：实际运行命令，生成输出、输入摘要和 evidence 行
python3 <skill-dir>/scripts/task.py run <task-dir> --acceptance A1 --evidence check-1 \
  --workspace <execution-root> --input <相关文件> --expect '<实际预期文本>' \
  --command '<验证命令>'
# 收口：生成候选并复用原有完成门
python3 <skill-dir>/scripts/task.py finish <task-dir>
```

严格任务还提供 `update`（更新进度、阻塞和恢复）、`capture`（非自动观察前采集相关输入）、`record`（登记实际取得的非自动验收或独立审查报告）和 `summary`（只读生成摘要）。具体参数和完整示例见[验证说明](skills/x-rail/playbooks/verification.md)。摘要核对相关输入，标明过期或无效；登记保留实际观察时间，另记登记时间。报告内容也绑定摘要。脚本不证明人工结论真实、审查独立或验收范围完整。

记录目标或授权变化、重要转向和交付；采用工作项时另按下方关键事件核对。原证据在相关输入和实际环境仍适用时复用；换会话不自动重跑。交接补恢复第一步和易错点，其他事实引用原记录。普通状态更新不刷新最后进展；新结论才用 `update --progress` 并说明原因。

`start` 拒绝覆盖已有状态；`run` 只接受 `verification_type: automatic` 验收；run/record 除原 required=yes 外，仅对 work_items_schema=1 清单中被 work_item.acceptances 引用的 required=no 可选验收开放登记，未引用的可选验收仍拒绝。record 仍只登记非自动验收或契约要求的审查；run 不替代人工、消费端、外部服务或独立审查；`finish` 不执行验证命令，只调用原有完成检查。每次 `run` 使用新的证据名，失败保留失败输出，旧证据不覆盖。`--used` 仅为兼容旧调用的可选观察值，写入 `tool_count_note`，不参与预算、完成门或效率结论。已有 `seal`、`check`、`complete --candidate` 入口仍可用。

严格任务顺序为：写契约、分配并登记 task-id、`start`、实施与取证、`run` 自动验证或显式完成人工验收、`finish`、更新索引。候选必须 `status: done`。失败保留正式状态、索引和候选。完成前再次核对契约、状态、候选字节和证据输入。解决当前未知的最短路径优先，不要求默认完整阶段链路；`review` 按风险、覆盖不足、需求分歧、用户要求或关键逻辑重改触发。单任务保持一个写入者。此机制防误操作，不抵御同等写权限的恶意执行者。

两个 shell 检查入口默认严格模式：

```text
bash skills/x-rail/scripts/check-contract.sh TASK_DIR [--draft|--ready|--seal|--locked] [--strict|--legacy-readonly]
bash skills/x-rail/scripts/check-state.sh TASK_DIR [--strict|--legacy-readonly]
```

退出码 0 为当前模式通过，1 为材料或验收失败，2 为参数或运行依赖错误。历史必须显式 `--legacy-readonly`，只读，不允许据此提交新完成，也不能封存。漏字段不会自动降级。不批量迁移历史任务，不补造过去快照。

新状态必须 `evidence_schema: 2`，绑定 contract_revision 和 contract_fingerprint。每条 passed 必需验收绑定唯一非空证据。`not_run` 可以没有证据文件，不能制造空白通过记录。

```text
required_verification: A1 status=passed evidence=evidence/check.txt
evidence:check|acceptance=A1|command=实际命令或人工核对|run_at=2026-10-10T02:00:00Z|result=passed|last_edit_at=2026-10-10T01:59:00Z|inputs=evidence/check.inputs.json|contract_revision=1
```

输入摘要记录版本、契约版本、绝对 workspace_root、相关文件相对路径、存在状态和原字节 SHA-256（内容摘要）。只绑定该项相关材料，允许无关文件变化。已删除文件记录 absent；状态、证据和快照不自我绑定。路径不能越界。命令文本是数据，校验器不执行。时间带时区，转换 UTC（Coordinated Universal Time，协调世界时）后比较。审查报告同样绑定输入、契约版本和时间，不能以旧报告为改后的代码放行。

`status` 为 `in_progress|done|blocked|stopped|cancelled`。完成要求全部必需验收、必需依赖、授权、快照、输入与预算通过。子任务 done 不自动通过父验收。证据只证明实际观察到的对象，静态文本不能证明模型会遵守。

## 工作项清单与状态

新严格实施契约在首个二级标题前采用 `work_items_schema: 1`。start 对 task_type=exec|bugfix 强制此字段；mixed/ops 等其他类型不由脚本猜测是否实施，但触发复杂度或范围条件的严格实施仍须显式采用，不能换类型绕过。其他严格任务按是否有清单采用，普通任务不使用这些字段。旧记录 check/update 兼容，实际需要清单时显式升级契约并保留快照，不自动迁移、不补造历史。

```text
# contract.md：R 是需求，W 是工作项，A 引用实际 Acceptance
work_items_schema: 1
requirement:R1|outcome=管理员可修改站点域名
work_item:W1|title=换址服务端|requirements=R1|depends=none|scope=src/domain.ts,tests/domain.test.ts|required=yes|acceptances=A1|skip_reason=none
# state.md：由 start 初始化，与契约工作项一一对应
work_item_state:W1|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none|unblock_condition=none|reason=尚未开始|next_action=先读相关服务和测试
active_work_items: none
```

每个需求至少被一项覆盖，每项至少关联一条验收；依赖无环，未知引用、重复标识或缺失状态拒绝。字段不含换行或 `|`，逗号分隔引用列表，标识符字母开头、仅字母/数字/下划线/连字符。工作项名称和范围走契约变更，执行者和进度走状态更新；工作项范围仍受契约限制。

工作项七状态是 `pending`、`in_progress`、`awaiting_verification`、`needs_fix`、`blocked`、`verified`、`skipped`，不混入整体五状态。实现已有先待验证，失败需修复；verified 要关联验收及证据当前有效，必需项不能跳过，可选项 skipped 自动引用契约非空且非 none 的 skip_reason，并保留本次 item-reason 动作说明。开放可选验收登记不改变契约 required 语义，不自动升为整体必过；引用它的工作项要 verified，仍须该验收 passed 且证据当前有效。必需工作项不能 skipped，可选工作项合法 skipped 不制造 passed。提交或子代理通知不是通过证据。输入变化只读摘要显示过期，不暗改状态；执行者退回待验证或需修复。

前置已验证、后继已在做时，若前置证据过期，可直接将前置退回待验证，无须先逐项阻塞后继；后继保留真实既有状态，不自动级联修改。启动或重新激活后继、进入 verified 及 finish/complete 时，仍检查前置已验证且证据当前有效。summary 只读标过期事实，不能沿用旧状态放行完成。静态定义继续校验引用和无环，不新增级联状态机。

```bash
python3 <skill-dir>/scripts/task.py update <task-dir> --item W1 \
  --item-status in_progress --item-owner parent \
  --item-reason '开始换址服务端' --item-next-action '读取换址服务和测试' \
  --next-action '读取换址服务和测试'
```

完整接口为 `--item`、`--item-status`、`--item-owner`、可重复的 `--item-evidence-ref`（任务内证据文件相对路径，如 evidence/check-1.txt；本次列表替换旧列表，不与 none 混用）、`--item-commit`、`--item-blocked-by`、`--item-unblock-condition`、`--item-reason`、`--item-next-action`。每次逐项更新必填原因及下一动作；未传值保留，清空显式传 none，整体参数仍表达整任务。详见[验证说明](skills/x-rail/playbooks/verification.md)。

开始、实现完成、新验证、审查返回、阻塞/解除、重要阶段、提交、压缩和交接前核对相关项。整体 next_action 只写第一动作，其余在各项；部分受阻不等于全部停工。active_work_items 由 in_progress 项自动生成并校验一致，支持多项；父状态仅主会话一个写入者。计划与交接引用原记录，不维护第二份状态。start 初始化清单，summary 只读输出覆盖、计数、阻塞、过期和就绪项；finish/complete 保留原完成门，另要求必需项 verified、可选项明确处理且无活动项，下一动作是交付/结束说明。

## 编码与用户结果验收

TDD（Test-Driven Development，测试驱动开发）像先写表单行为检查，再让代码满足它：先观察目标行为失败，再写最小实现、通过并整理。新增或改变条件、解析、权限、金额和数据写入等非平凡逻辑默认采用；纯文档、文案、简单样式采用内容或渲染核对。复用项目测试工具，细节见[执行说明](skills/x-rail/playbooks/exec.md)。

测试保护对应代码行为。影响用户流程时还需按验收沿登录、页面入口、操作、请求和结果检查必要路径。代码写入、检查通过、使用路径已验证、当前任务全部必需验收满足分别报告。没有先失败与后通过证据，不声称使用了测试驱动开发；完成任务不自动包含上线。

## 取证与轻量文档

[document-task.md](skills/x-rail/templates/document-task.md)只供严格记录的既有材料整理使用。普通文档直接列目标、依据、范围和验收，先读后写，核对后交付，不为流程创建目录。严格文档先写契约，再用 `task.py start` 生成状态；只为具体缺口补读。6 次资料动作、20 次总动作是检查点，不是宿主自动拦截。合并命令仍按实际动作计数。明确未执行的测试不得写成已执行。

大输出先工具内统计、筛选或索引。预计超过 8KB 的工具输出先保留原始结果到任务允许的证据路径，上下文只带命令、退出码、通过数量、失败测试名或失败摘要和证据路径；不能判断全局结果时停止，不用尾部截断掩盖失败。相互独立、无共享写入、无前置依赖的读取或检查尽量同轮合并；有顺序依赖、共享资源或副作用时保持串行，并说明原因。共享文件、数据库、缓存和构建目录保持单写入者。调用 `/x-rail` 即授权当前目标范围内默认主动委派；目标、读写范围与验收明确时，默认把完整执行单元交给子代理，不等逐次点名。独立且资源隔离的项可并行，有依赖项在前置满足后接力；不可并行或文件共享不是父会话包办理由，共享写入由同一子代理承接。短小且主会话已掌握材料、交接成本明显更高时直接完成；紧密耦合的实现由同一位执行者承接。主会话负责共享约定、调度、集成和最终验收。用户禁止、更高规则或宿主限制优先。细则见[执行说明](skills/x-rail/playbooks/exec.md)。

使用 [child-task.md](skills/x-rail/templates/child-task.md) 固定工作项、输入、允许路径、依赖、验收、权限、成本和正式输出绑定。子代理总时限沿用宿主与代理配置，默认省略 `timeoutMs/maxRuntimeMs`（子运行总时限覆盖参数），不另设运行倒计时；仅当前用户明确要求或更高优先级规则强制时传入并记录来源。任务记录总期限、无进展阈值和单条验证命令超时不转换成子代理总时限。实现者独立副本，共享接口、配置与父状态唯一写入者；测试数据库、缓存、构建目录也明确所有权。一项完成重查后续就绪项，不等待无关整批；派发后继续独立工作，无独立工作交还控制权等原生通知，仅在依赖处汇总。父会话核对产物、差异和实际验证再更新父状态，通知不自动通过验收。基础设施失败立即报告并暂停原依赖，不换协议、不自动重发、不冒充独立审查。

实现自检后固定输入，审查集中交回必修问题，集中修复并重跑受影响检查；优先恢复原审查运行定向复核，不可恢复记录原因并按宿主规则替代。不能替代必要的独立最终审查，不能把必修改可选；相关代码或报告变化更新证据，无关文件不自动使全部证据失效，状态不作为代码审查输入。

## 预算与恢复

当前用户明确说“解除成本限制”“不限制成本”“不计成本”等时，本任务持续不限成本，阶段切换、恢复和已授权委派都沿用。取消技能默认费用、调用/资料次数、总时长上限和文档 6/20 次收口；同范围执行费用不重复确认。无进展、重复错误、必需验收和敏感操作边界仍生效；宿主或账户硬限制只能报告，技能不能取消。否定句、引用、假设和“解除阻塞”不构成授权；新购买或订阅仍单独确认。

严格任务在 contract 顶部记录 `cost_control: unlimited` 和 `cost_authorization: 当前用户原话及来源`；`start` 生成 `budget: unlimited`，不加默认总期限。旧任务按契约版本规则登记授权，检查器不再以旧数值预算或总期限超限阻断。来源是否真实由执行者核对，脚本只检查记录。普通任务沿用当前授权，不为此创建状态。

未解除成本限制时，普通任务按实际完成条件验证，不创建预算状态。严格任务保留 L1/L2/L3 的 60/150/400 离线记录提示；未接入宿主真实计数时，不填写人工动作数，也不把提示当作效率证明或完成门。无进展提醒为 20/60 次；长任务另有 30 分钟无进展和 8 小时总上限。真实计数不可用时，依据连续无进展、重复错误、时间和验证失败判断是否暂停。暂停和等待用户分开记录。

成本总量、上下文容量、模型请求超时、工具/子运行超时与无进展分开报告。容量用宿主实际信号，未知就写未知，不编百分比或凭感觉宣称“预算耗尽”；模型请求超时不能套用工具 timeout。停止保留准确错误、原运行、产物、已知/未知和恢复第一步。

恢复续用原任务编号，阶段、提交、会话或工作项变化不新建任务。读取索引、contract、state、最近 checkpoint、handoff、audit/runs.json、相关 evidence；核对工作区、版本、未提交差异和输入。原外部运行先查再恢复，不可查时 unknown 或 blocked，不重复启动。[long-task.md](skills/x-rail/templates/long-task.md)给依赖和运行引用格式。

## 本地执行前沿与持久接收

按交付性质选择普通执行、单目标持续推进、复杂定制流程或长期协调。组织方式按真实需要伸缩，不按文件或模块数量分档。证据模式复用 contract/work_items、state 七状态和当前输入摘要；阶段3普通 Markdown 清单检查继续可用，但不能替代证据模式完成门。

```bash
python3 skills/x-rail/scripts/task.py frontier <task-dir>
python3 skills/x-rail/scripts/task.py inbox <task-dir>
python3 scripts/demo-coordination.py
```

`frontier` 只读输出 JSON 就绪集合、运行/待验证/过期/终态及依赖和资源冲突原因，检查传递依赖、必要审查与当前证据；目录、父子路径和不确定 glob 保守串行。它不启动代理、不修改状态、不代替 finish。`dispatch/notify/inbox/consume` 保存原运行、派发输入版本、通知和消费事实，工作项状态仍只在 state.md。重复通知幂等，旧运行/输入变动结果拒收，消费 accepted 不等于 verified。

循环为前沿 → 宿主派发 → 通知入队 → 安全节点核对消费 → 原证据命令与 update → 重算补位。脚本不发模型请求、不后台等待；遵 Pi 原生协议。系统性基础设施失败先停派、暂停整体，保存准确错误、原运行、产物与恢复第一步；单项失败不阻塞独立兄弟项。冷启动先 inbox 和原运行查询，不重复启动。

完整命令与分类恢复见 [协调说明](skills/x-rail/modules/orchestration.md)，交接见 [协调模板](skills/x-rail/templates/coordinator-handoff.md)。演练仅模拟宿主事件，保留每条公开 CLI 回执；不证明真实多模型服从、跨日稳定性、费用或提速。

## 自检与验证

```bash
python3 skills/x-self-check/scripts/analyze_sessions.py --sessions-root <日志目录> --days 7 --timezone Asia/Shanghai --format json
python3 scripts/test-task-checks.py
python3 scripts/test-work-items.py
python3 scripts/test-task-checklist.py
python3 scripts/test-frontier.py
python3 scripts/test-coordination.py
python3 scripts/test-repo-boundary.py
python3 scripts/test-skill-xml.py
python3 scripts/test-self-check.py
python3 scripts/test-html-check.py
bash scripts/test-worktree.sh --keep-artifacts
bash scripts/test-contract.sh --keep-artifacts
bash scripts/test-fixtures.sh
bash scripts/test-v2-lifecycle.sh
bash scripts/test-flow.sh
bash scripts/test-skill-metadata.sh --keep-artifacts
bash scripts/test-document-template.sh
bash scripts/test-install.sh --keep-artifacts
```

`--days 21` 支持三周；指定窗口用成对带时区的 `--start/--end`，结束不包含。脚本只输出，不联网、不执行日志命令。默认摘要不输出提示、命令正文、邮箱或密钥。历史版本缺失写 null，不用当前文件代替。

核对任务记录时成对给 `--task-root <任务目录集合>` 和 `--task-mode strict|legacy-readonly`，目录可重复。只核对明确关联编号，输出检查器内容摘要和记录字节一致性；历史格式失败不表示交付失败。没有显式模式不读取任务记录。

测试使用全新目录并保留产物。`--test-root DIR` 指定目录必须是新目录。删除型安装回归等待具体授权。结构、确定性行为、真实模型演练分别验收；没有模型演练证据不能称全部版本完成或稳定提速。

详细说明见 [架构](docs/architecture.md)、[文件边界](docs/file-boundary.md)、[审查委派](docs/review-delegation.md)和[会话场景](docs/session-scenarios.md)。[PStack 设计参考](docs/pstack-design-reference.md)仅供修改或调整 x-rail 本身时按需读取；会话中仅使用 x-rail 相关技能处理任务时不读取，不作为前置阅读或自动加载材料。
