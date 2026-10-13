# 验证说明

这份说明把“能不能交付”比作验收一条网页功能：先看零件装对，再看插口能用，再沿用户路径走完，最后确认交给别人后能照做。五类观察面不是新的任务等级；契约仍只使用现有 `layer`（验证所处环境）和 `verification_type`（谁/怎样验证）。

## 普通任务与严格记录

普通任务说明目标、范围、完成条件和必要检查，读取相关材料后执行。实际输出与预期相符才交付；不为了证明流程创建契约、摘要和候选。用户已有严格任务记录时继续原记录，不能降级。

严格任务用以下命令减少机械填写；任务目标、验收内容、授权和审查策略仍由执行者依据用户请求填写。

```bash
python3 <skill-dir>/scripts/task.py start <task-dir>
python3 <skill-dir>/scripts/task.py run <task-dir> --acceptance A1 --evidence behavior-1 --workspace <execution-root> --input src/changed.py --input tests/test_changed.py --expect 'Tests 4 passed' --command 'python3 tests/test_changed.py'
python3 <skill-dir>/scripts/task.py finish <task-dir>
```

- `start`：从已写好的 contract.md 生成 state.md，使用当前时间、契约摘要、not_run 验收和离线记录提示，封存并校验。已有状态拒绝重建；不补过去快照。
- `run`：仅处理 required=yes 且 verification_type=automatic 的验收。执行前生成相关输入摘要；在指定工作区实际执行命令，核对退出码和全部 `--expect` 文本。命令输出、完成时间、输入摘要和证据行由脚本写入；输入在执行期间改变则拒绝更新正式状态。人工、消费端、外部方式和独立审查仍单独核对，不能用此命令冒充。
- `--input`：可重复，只绑定当前验收相关文件；必须至少声明一个文件；确实缺失的文件记录 absent。目标文件、测试和必要依据应一起绑定，不能只选一个无关文件；不绑定状态、证据、快照和候选。输入集合由执行者声明，程序校验摘要，不能替执行者判断材料是否完整。
- `--expect`：可重复，必须是命令实际输出中的预期事实；不能只写“退出 0”。文本包含关系不能证明完整行为，命令应包含真正检查结果的测试或脚本。输入集合由执行者声明，不能自动证明完整；机器可读测试结果优先于宽泛文字匹配。
- `--used`：兼容旧调用的可选观察值。它只写入 `tool_count_note`，不参与预算、完成门或效率结论。没有宿主真实计数时不要填写。
- `finish`：从当前状态生成唯一候选，调用原 complete 的全部检查。只生成完成时间，不刷新旧验证时间，不修改验收、审查或授权。失败保留正式状态与索引，候选留在 tmp/。

证据文件名每次验证使用新名称；旧记录不覆盖。`run` 的默认超时为 300 秒，可用 `--timeout` 调整；超时保存失败输出并终止该命令进程组。check/complete/finish 只核对资料，不执行证据里的命令。初始化和完成不包含提交、发布或数据库操作。

## 固定状态与非自动验证命令

像提交前端表单一样：执行者判断内容，脚本处理字段、时间和保存。严格任务更新阶段、下一步、阻塞和恢复用 `update`，非自动验收或审查用 `capture` 和 `record`，读取当前结果用 `summary`。普通任务继续直接验证和交付。

```bash
# 更新下一步，不刷新最后进展时间
python3 <skill-dir>/scripts/task.py update <task-dir> --stage review --next-action '核对用户入口'
# 新结论或可用交付才声明实质进展，不用于单纯更新时间
python3 <skill-dir>/scripts/task.py update <task-dir> --progress --reason '已定位入口权限根因' --next-action '验证对应用户创建路径'
# 阻塞与恢复；恢复不清除旧证据、不自动刷新进展
python3 <skill-dir>/scripts/task.py update <task-dir> --status blocked --blocked-by '外部服务不可用' --unblock-condition '服务可访问' --next-action '查询原服务状态'
python3 <skill-dir>/scripts/task.py update <task-dir> --status in_progress --reason '服务已恢复' --next-action '验证用户入口'
# 人工、用户实际使用、外部方式：先保存相关输入，再实际观察
python3 <skill-dir>/scripts/task.py capture <task-dir> --evidence observation-1 --workspace <execution-root> --input <相关文件>
# 实际观察后，将结果保存为任务内报告；参数必须使用真实结果与观察时间
python3 <skill-dir>/scripts/task.py record <task-dir> --acceptance A1 --evidence manual-1 --report evidence/observation-1.md --inputs evidence/observation-1.inputs.json --observed-at <带时区的实际观察时间> --result passed --observation '实际逐项核对动作和结果'
# 独立审查用相同登记命令，但绑定审查者及实际运行或报告来源
python3 <skill-dir>/scripts/task.py record <task-dir> --review --evidence review-1 --report evidence/review-1.md --inputs evidence/observation-1.inputs.json --observed-at <实际审查时间> --result passed --observation '实际审查内容' --reviewer <真实审查者> --source <原运行或产物来源>
python3 <skill-dir>/scripts/task.py summary <task-dir>
```

- `update` 只允许阶段、下一步和合法非完成状态变化。暂停必须有原因、解除条件、第一步；恢复必须有原因和下一步。done 和 cancelled 不重开。完成仍用 finish；目标、授权和验收变化仍走契约版本规则。仅更新字段不刷新最后进展，`--progress` 必须说明新结论；脚本不能证明该结论真实。
- `capture` 在观察前保存相关输入摘要及 captured_at（采集时间），不更新状态、不覆盖旧摘要。相关材料变化需重新采集并重新观察，不能给旧结论补新摘要。
- `record` 只登记必需非自动验收或契约要求的审查；不运行验证、不判断报告质量。报告须为任务内非空文件。它保留 observed-at（实际观察时间），另写 recorded_at（登记时间），要求采集不晚于观察、观察不晚于登记，并再次核对输入。报告内容摘要也保存，后续更改报告不能仍按原结论放行。passed、failed、blocked 分别记录；未执行保持 not_run，不造空报告。人工登记参数本身不是事实证明。
- 独立审查先获得委派授权，再向审查者提供采集绑定的输入，取得真实报告后登记。reviewer 和 source 只是可追踪来源，不证明独立性；主会话自查不能冒充独立审查。旧审查记录留在证据历史，当前指针只选最近实际判定。
- `summary` 只读生成目标、范围、阶段、必需验收、证据路径、审查、阻塞和下一步。相关输入变化显示 stale（过期），记录或报告不符显示 invalid（无效），不写回 state；记录中的 done 不代替当前证据核对。外部环境和时效变化还需执行者判断。严重格式或契约错误可明确报错；摘要不单独证明任务完成。
- 旧相关输入过期时允许 update 记录阻塞、run 或 record 获取替代证据；默认 check、complete、finish 仍核对所有必需当前输入。不能用维护状态的路径绕过完成检查。

目标和授权在 contract，当前进展在 state，实际结果在 evidence，重要决定在 audit。摘要和报告从原记录生成，不要求每次同步多份文本；交接只补恢复第一步、易错点和引用。只在目标或授权变化、新验证结果、重要转向、阻塞或交接、交付时记录。阶段变化影响恢复时合并更新，普通读取或命令不单独记账。

## 编码方法与完成标准

测试驱动开发先写目标行为检查，观察准确失败，再写最小代码、验证通过并整理；适用范围见 exec.md。它保护代码行为，但不能代替用户流程验收。改动影响用户流程时，按当前任务要求核对登录、页面入口、操作、请求和结果，以及必要拒绝路径。

例如新增创建权限：内部函数检查通过后，还要用对应用户从页面点击创建，核对请求实际到达正确判断、结果归属正确，并验证越权或超额拒绝。自动测试可以覆盖这条路径；不足部分才补真实环境或人工检查。验证强度取决于需求和失败影响，不要求每次小改动跑所有环境。

代码已写入、对应检查通过、使用路径已验证、全部必需验收满足，分别报告。文档任务以准确可用文档为交付，并说明测试未执行；开发任务需要实际实现和相应行为证据。完成不自动包含上线。没有先失败、后通过证据，不声称使用测试驱动开发。

审查或恢复先核对原结果、证据、当前相关输入及限制。相关输入、外部环境或时效要求变化时，只重跑受影响检查；换会话本身不导致证据失效，也不能从当前机器缺环境推断过去未验证。

## 启动摘要最小示例

```text
当前阶段：exec；已通过契约校验，按计划实施；状态 in_progress
任务：补充阶段入口和验证规范；done_when 为 required 验收全部有新鲜证据
风险：medium；会改工作流文档和检查脚本；review_policy=user-confirm（交付需只读审查证据）
允许改动：skills/x-rail/**、scripts/test-flow.sh；不改业务代码和历史任务
禁止动作：不推送、不发布、不修改项目外安装副本；交付前需完成只读审查
必过验收：A1/A2 已通过；A3/A4/A5 未运行
已有证据：evidence/flow.txt 支持 A1；尚无运行层证据
当前阻塞：未记录
下一步第一动作：运行 scripts/test-flow.sh 并写入 evidence/flow.txt
```

如果 `contract.md` 没有 `risk` 或旧任务没有 `required_verification`，写“未记录”，不能根据任务名猜测。摘要只读 `contract.md`、`state.md`、checkpoint 和 evidence；它不是新的状态文件。

## 五类真实使用面

| 观察面 | 大白话 | 正确示例 | 反例 | 常见 layer |
|---|---|---|---|---|
| 代码层 | 看零件有没有装对 | 类型检查通过；执行单元测试并核对新增分支的实际结果 | 只看到命令退出码为 0，没有看测试计数或断言 | `syntax/config`、`static`；执行测试为 `runtime/local` |
| 接口层 | 看按钮或插口能不能用 | 调用命令行入口，传入合法参数，核对输出字段和错误码 | 只 grep 出函数名，没调用入口也没核对响应 | `static`、`runtime/local` |
| 流程层 | 按用户路径走一遍 | 从创建契约到写 evidence、更新 state、通过完成门走完整链路 | 只验证中间脚本，跳过状态更新和完成门 | `runtime/local`、`consumer` |
| 运行层 | 在实际环境里试用 | 在本地服务或浏览器中操作，核对用户看到的页面/结果 | 仅凭静态配置或 mock 推断真实环境可用 | `runtime/local`、`external` |
| 交付层 | 看交给别人后能不能照做 | 新会话只读 handoff，能执行 `next_action` 第一条并找到证据 | 文档写了“已完成”，但没有路径、命令或回滚步骤 | `consumer`、`static` |

## Acceptance 的写法

每条新增或调整的验收条件至少明确三件事：

1. **观察对象**：用户、下游系统、命令输出、页面、文件状态或外部服务看到了什么。
2. **预期结果**：通过时应该出现什么，失败时应留下什么证据。
3. **验证动作**：谁在什么环境中，用什么命令或操作核对。

示例：

```text
outcome: 新会话能从 handoff 找到任务状态、证据位置和第一步动作
verification: 只读 handoff、state 和最近 checkpoint，执行 next_action 第一条并记录输出
verification_type: consumer
layer: consumer
required: yes
```

只运行命令但没有观察预期结果，证据不能写成 `passed`。无法运行时使用现有状态：尚未执行为 `not_run`，实际结果不符为 `failed`，权限/服务/前置条件阻断为 `blocked`。不要为了满足完成门降低 `required` 或把较低层证据冒充真实使用面证据。

## 现有验证层的含义

| layer | 它能证明什么 | 结果示例 |
|---|---|---|
| `syntax/config` | 代码能解析、类型或配置结构正确 | 类型检查输出通过；不推断按钮行为 |
| `static` | 文件内容和静态约束满足要求 | 核对文档覆盖、技能头部；不推断服务可用 |
| `runtime/local` | 本机实际执行时的行为 | 单元测试、命令行入口、任务生命周期和本地浏览器操作达到预期 |
| `external` | 外部服务、账号或权限在实际环境可用 | 真实请求响应符合预期；凭据不足写 blocked |
| `consumer` | 用户或下游使用产物时能达到目标 | 从交接文件找到并执行第一步；不只检查文件存在 |

## `layer` 与 `verification_type` 的区别

`layer` 是环境位置，`verification_type` 是验证方式。例如：自动调用外部服务是 `automatic + external`；人工在本地走恢复流程是 `manual + runtime/local`；下游使用生成的操作手册是 `consumer + consumer`。两者必须按实际证据填写，不能因为检查脚本是自动运行就把所有结论标为 `automatic`。
