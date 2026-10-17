# Execute Playbook

<stage name="exec">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；严格任务才读取 contract/state 并保留 evidence/audit。用户授权的目标文档写指定位置。公共生命周期规则以主入口为准。

适用场景：已有通过校验的契约或实施计划，需要在允许范围内修改目标文件并完成验证。
输入：contract、state、实施计划、目标文件、调用方、测试和当前工作区基线。
输出：最小变更、真实验证输出、证据文件、未验证项和可交接状态。
不做什么：不超出契约范围，不用编译成功替代行为验证，不在失败后原样重复同一策略。
停止条件：required 验收和对应证据满足完成门，或遇到阻塞、越界、决策变化而停下并记录。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before broad exploration. For an existing task, read contract, plan, state, target files, callers, tests, current differences, and the workspace baseline (cwd, branch/worktree, pending changes). If a model request times out, record a recovery summary in `audit/` before continuing.
2. If the contract uses v2 format, run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before editing; do not execute against an incomplete contract.
3. 先核对工作项清单及覆盖；复杂或大范围实施必须拆分并持久记录，不按需求数量判断。已有计划复用，新严格实施采用 work_items_schema: 1。start 对 task_type=exec|bugfix 强制此字段；mixed/ops 等其他类型不由脚本猜测是否实施，但触发复杂度或范围条件的严格实施仍须显式采用，不能换类型绕过。旧记录 check/update 兼容，按需显式升级契约并保留快照，不自动迁移或补造历史；普通局部任务仍可用会话内清单，只读分析不落盘。List the current logical change and its required verification before editing. Read only the target symbols and their callers first; expand to full files only when a specific Acceptance condition requires it.
   新增或改变条件、解析、权限、金额、数据写入等非平凡逻辑，默认采用 TDD（Test-Driven Development，测试驱动开发）：先写行为测试，确认它因目标行为缺失而失败，再写最小实现，确认同一测试和相关回归通过，最后在测试保护下整理代码。导入或环境错误不能代替目标行为失败。优先复用项目测试工具，不新增框架。纯文档、文案、简单样式和不改行为的低风险修改采用内容或渲染核对；真实设备或外部服务不能自动化时记录实际观察和限制。用户明确要求优先。
4. Modify only files inside the task boundary. User project files are targets; workflow records stay in `.work-docs`.
5. Verify from narrow to broad: `syntax/config`, `static`, `runtime/local`, `external`, `consumer` as required by the contract. A manual, consumer or external condition must be explicitly recorded rather than silently treated as automatic.
   对影响用户流程的改动，按任务验收沿实际入口检查：对应用户登录 → 页面入口 → 操作 → 请求 → 预期结果；核对必要的越权或超额拒绝。测试数量不替代入口结果。没有预先失败和实现后通过证据，不声称使用了测试驱动开发。严格任务自动验证用 run；非自动验证先 capture，观察后 record，状态变化用 update；命令细节见 verification.md。
6. If a contract condition changes, increase `contract_revision`, record old/new value, reason, approver and affected evidence before continuing.
7. After a failed verification, record the strategy fingerprint and use a materially different strategy. Three consecutive required failures trip the circuit breaker.
8. Preserve real output in `evidence/`; decisions and checkpoints go to `audit/`。开始、实现完成、新验证、审查返回、阻塞/解除、重要阶段变化、提交、压缩和交接前核对相关工作项，目标或授权变化走契约变更。普通读取和每行编辑不更新；状态改字、换执行者或更新时间不算真实进展。整体 next_action 是第一可执行动作，其他待办留在各项；某项 blocked 而其他项能继续时，整体保持可推进状态。交付初稿、实现完成、验收通过分别报告。
9. Apply the done gate. Never infer completion from exit code, build success, file existence or agent report alone. 工作项实现后先 awaiting_verification；关联验收及当前证据满足才 verified。全部必需项已验证、可选项明确处理后仍须通过原验收、审查、授权和依赖门。

## 完整执行与接收

以下六条是完整执行、委派与接收的规则来源；普通／严格记录及长模式仍按主入口判断，使用子代理或内部先后关系本身不改变模式。权限与费用按主入口 authority、cost_policy，失败与原运行恢复按 recovery，证据与完成门按 verification 和 playbooks/verification.md；不另建分类、账本或状态。

1. **先定结果。** 先读最小相关材料与调用方，明确目标、允许范围、必要输入和验收，复用已有计划。工作项定义交付，下一动作说明当前做哪部分。范围、风险或验收变化时，执行者先暂停扩大改动，由主会话核对并按现行授权与契约规则调整边界及下一动作，保留已有修改和有效证据；直接执行时主会话承担同一责任。批量方法尚未跑通时，以第一项验证说明、实施、验收和接收；已有当前有效同类证据直接复用。
2. **主动交接。** 调用 x-rail 即已获当前目标范围内委派授权；宿主可用、目标与读写范围及验收明确时，默认将完整执行单元交给子代理完成调查、实现和相关测试，不等用户逐次点名。独立且资源隔离的项可并行，有依赖项在前置满足后接力；不可并行或文件共享不是父会话包办理由，共享写入由同一子代理承接。短小且主会话已掌握材料、交接成本明显更高时直接完成；紧密耦合的实现由同一位执行者承接。边界不清先整理，不按文件或命令机械拆代理，也不先由主会话完整调查再交出实现。主会话负责共享约定、调度、集成和最终验收；并发数按任务与宿主能力，不固定数量。适合并行却串行时记录具体原因；用户禁止、更高规则或宿主限制导致不能委派时，记录准确原因并由父会话直接执行。
3. **隔离写入。** 共享文件、父状态、分支、数据库、缓存和构建目录只有一个写入者；并行写入使用独立副本，分配前核对测试副作用与环境所有权。新独立工作需隔离历史时使用宿主实际支持的新上下文，核对宿主实际模式，不凭新运行标识推定隔离。原工作先核对原清单、状态、工作区和证据，原运行先查询再恢复；已结束消费原产物，可恢复续接，不可查记 unknown/blocked，不重复启动或用新运行绕过现场。子代理总时限沿用主入口 work_items 的宿主配置规则，不另设固定并发或运行倒计时。
4. **精简返回。** 用 ../templates/child-task.md 传完整目标、输入、依赖、权限、成本、验收及正式输出绑定。执行者返回结果、实际修改位置与版本、后继必要约定、验证命令与结果及证据引用、偏差、未解决风险、下一步和原运行位置。大量原文留执行侧，引用须实际可访问，关键失败与限制不能省略。主会话在安全节点接收通知，核对产物后更新原工作项；通知不自动通过验收。一项完成即重查就绪项，有可推进工作及时接力或补位，不等无关整批；无独立工作则交还控制权等原生通知，仅在依赖处汇总。只有宿主允许且同轮确需非通知结果时显式等待。
5. **按缺口核验。** 主会话核对实际产物、范围和当前证据，按异常、接口冲突或覆盖不足展开资料，避免重做整项实现。执行者已完成且仍适用的检查直接复用；接入实际交付工作区后核对相关输入、环境和组合影响，补受影响检查，不因无关变化重跑全部。独立审查针对自动覆盖尚未解决的具体风险，现行中高风险和契约必需独立审查继续履行，不能凭自报或提交号放行，也不能由主会话核对冒充独立审查。
6. **达到验收就交付。** 开始前明确观察对象、必要检查与结束条件，集中处理阻止交付的问题。实现与自检后固定输入，必要审查集中交回必修问题；集中修复后定向复核必修问题及受影响部分，满足全部约定验收即结束，非阻塞建议留后续，不把必修改可选。不默认叠加多轮全量审查，既有必需最终审查仍须完成。优先恢复原审查运行定向复核，不可恢复记录原因并按宿主规则替代；原审查复核不能代替要求的独立最终审查。相关输入或报告变化更新对应证据，进度文件不作为代码审查输入。

基础设施错误立即暂停依赖并保存准确错误、原运行及已有产物，不换协议或前后台。成本总量、上下文容量、模型请求超时、工具/子运行超时与无进展按主入口 recovery 分别报告；容量只用宿主实际信号，未知写未知，不以工具 timeout 解释模型请求超时。压缩/交接前保存恢复第一步，恢复后核对原编号、状态和输入。
持续目标、复杂定制与长期协调见 ../modules/orchestration.md。frontier 重算，通知先入队后核对消费；dispatch/notify/inbox/consume 不启动模型、不更新工作项、不替代原证据与完成门。</procedure>
  <quality_check>先失败反例后最小实现；共同变化逻辑只维护一处，接口保持小。项目规范优先，非 TypeScript 不注入专用规则。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
