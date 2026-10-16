# Plan Playbook

<stage name="plan">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；严格任务才读取 contract/state 并保留 evidence/audit。用户授权的目标文档写指定位置。公共生命周期规则以主入口为准。

适用场景：需要把已确认目标拆成可执行、可验证、可交接的实施步骤，或整理已确定材料。
输入：已批准的目标、范围、契约、验收条件、风险策略和固定材料。
输出：逐任务实施计划，或轻量文档交付；每项工作都有文件范围、验证方式和预期结果。
不做什么：不在缺少目标或决策门未通过时偷偷进入实施，不把“写了计划”当成代码已验证。
停止条件：计划能被另一位执行者独立执行，或轻量文档已覆盖材料且明确测试未执行。

先区分交付：逐任务实施规格走「实施计划分支」；基于已确定材料的测试用例、检查清单和变更说明走「轻量文档分支」。不新增阶段，两者 task_type 与 stage 都是 plan。未确定功能不归入轻量分支。

## 轻量文档分支

先沿用主入口 cost_policy：当前用户明确不限成本时，取消下方 6 次资料读取、20 次总调用的次数收口与默认总预算；按实际缺口推进，保留无进展和必需验收检查。

1. 一次确定交付物、依据、不做什么、完成条件。默认 L1；依据优先使用用户指定方案版本和固定提交，未指定提交时记录本次采用的提交及未提交改动是否纳入，不默默忽略用户修改。风险单独判断。
2. 普通文档直接读取固定依据并写初稿；需要严格记录时从 `templates/document-task.md` 填契约，优先 `task.py start` 生成状态并校验。只读整理通常低风险、auto；中高风险遵守对应审查，确认仅按敏感动作。默认按模板调用校验器，只有准确报错涉及格式、或任务确需改变格式时才读校验器源码。
3. 默认读取方案行为要求、计划验收表、固定提交摘要、相关测试名称与必要断言。主材料读取原则上控制在 **6 次资料工具调用**以内，按实际读取动作计数；批量包裹或一个命令读多份材料不能绕过。材料足够立即写初稿；到检查点仍不足，先写已有条目和具体缺口。确需继续读大材料时，先在 state 的 next_action 指明尚未覆盖的验收条目，再只读该条目，不重新讨论路由。
4. 初稿写用户授权位置；严格任务的内部产物才写 outputs/。测试用例默认列：场景、前置条件、操作步骤、预期结果、优先级、依据。其他文档按目标选择最小可检查结构。可以标注待确认项，但不能以个别细节为由延后整份初稿。
5. 每次补读前指出要确认**初稿中的哪条预期结果或事实缺口**；无法指出则停止扩展读取。默认不搭环境、不代跑、不全量审查、不检查发布；环境细节不是整理行为用例的前提。真正改变必过预期的缺口不能用猜测填补。
6. 当前工作区合并或冲突只记录为执行前提，继续以固定依据整理；仅当其改变纳入范围的预期结果时读取局部差异，不追踪操作人或连续扫描修改时间。
7. 达到 **20 次总工具调用**时必须收口判断：验收齐全则交付；仅可选细节缺失则说明后交付；必过事实缺失则保持非 done，交付已整理内容、具体阻塞与下一步。**必过项不能降为可选项**，部分初稿不能标为完成。原预算、无进展熔断仍适用；这些检查点**不是宿主自动拦截**。
8. 对照依据检查覆盖与事实，逐条检查步骤/预期/依据是否清楚；普通文档在回复报告核对结果，严格任务才记入 evidence/coverage.txt 与 evidence/clarity.txt。关键词命中只算静态检查，不能替代内容核对。严格任务通过完成检查后交付；测试用例明确「用例已整理，测试未执行」。若用户要求实际执行，单独进入执行流程并确认范围，不在文档任务中偷跑。

## 实施计划分支

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before broad exploration. For an existing task, read its contract and state first. If a model request times out, record a recovery summary in `audit/` before continuing.
2. Copy the approved `objective`、`done_when`、`scope`、`forbidden`、`risk` and decision gates; do not broaden scope.
3. If the contract uses the v2 format, copy every numbered `Acceptance` condition and preserve its verification type and layer.
4. 按逻辑独立性、复杂度、范围和依赖拆成可独立验证的工作项。多个独立复杂逻辑、单个大范围需求、单需求的多步状态/权限/并发/写入或协作依赖，均先拆分并持久记录，不按五个、六个需求计数。局部简单同源改动可合项，写清依据；只读分析在回复列项，不落盘；用户只要方案文档时只写授权位置。已有合格计划先核对并复用。
5. 新严格实施在契约顶部写 `work_items_schema: 1`；start 对 task_type=exec|bugfix 强制此字段，mixed/ops 等其他类型不由脚本猜测是否实施，但触发复杂度或范围条件的严格实施仍须显式采用，不能换类型绕过；每个 requirement 有稳定标识和可观察 outcome，每个 work_item 有 title、requirements、depends、scope、required、acceptances、skip_reason；执行者及下一动作由 state 记录。每个需求至少被一项覆盖，每项至少关联一个验收；依赖无环，共享写入有唯一责任人。必需项 required=yes、skip_reason=none；可选项 required=no 并预写非空且非 none 的 skip_reason，skipped 自动引用该理由并保留本次 item-reason 动作说明。完整结构见 verification.md。工作项不是需求编号或验收结果，任务内计划只引用工作项，不维护第二份进度。旧记录 check/update 兼容，需要清单时显式升级契约并保留快照，不自动迁移或补造历史。
6. Include the done gate, contract revision and circuit-breaker thresholds.
7. Write the implementation plan to `.work-docs/tasks/&lt;task-id&gt;/outputs/` and state the first executable action. 普通小任务仍可用会话内清单；复杂/大范围实施沿用严格状态与证据，拆分本身不触发长模式或委派授权。
8. 委派按执行说明的完整执行规则：已有委派及相应费用授权、宿主可用、目标与读写范围及验收明确时，默认交出完整执行单元；独立且资源隔离的项可并行，有依赖项在前置满足后接力；短小且已掌握材料、交接成本明显更高时直接完成。计划分配固定输入、允许路径、执行者、正式输出和环境所有权；共享约定与集成由主会话负责。未获授权则记录权限原因，不能从拆分推导委派权。</procedure>
  <quality_check>固定方案、提交或明确未提交差异；先覆盖清单与初稿；补读只回答具体缺口。默认不搭环境、代跑、追踪别的会话。写方案按需 technical-writing 与 unslop。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
