# Plan Playbook

## 阶段入口

适用场景：需要把已确认目标拆成可执行、可验证、可交接的实施步骤，或整理已确定材料。
输入：已批准的目标、范围、契约、验收条件、风险策略和固定材料。
输出：逐任务实施计划，或轻量文档交付；每项工作都有文件范围、验证方式和预期结果。
不做什么：不在缺少目标或决策门未通过时偷偷进入实施，不把“写了计划”当成代码已验证。
停止条件：计划能被另一位执行者独立执行，或轻量文档已覆盖材料且明确测试未执行。

先区分交付：逐任务实施规格走「实施计划分支」；基于已确定材料的测试用例、检查清单和变更说明走「轻量文档分支」。不新增阶段，两者 task_type 与 stage 都是 plan。未确定功能不归入轻量分支。

## 轻量文档分支

1. 一次确定交付物、依据、不做什么、完成条件。默认 L1；依据优先使用用户指定方案版本和固定提交，未指定提交时记录本次采用的提交及未提交改动是否纳入，不默默忽略用户修改。风险单独判断。
2. 从 `templates/document-task.md` 填写最小 contract.md 和 state.md，运行 check-contract.sh 后再广泛读取。只读整理通常低风险、auto；中高风险仍遵守确认和审查门。默认按模板调用校验器，只有准确报错涉及格式、或任务确需改变格式时才读校验器源码。
3. 默认读取方案行为要求、计划验收表、固定提交摘要、相关测试名称与必要断言。主材料读取原则上控制在 **6 次资料工具调用**以内，按实际读取动作计数；批量包裹或一个命令读多份材料不能绕过。材料足够立即写初稿；到检查点仍不足，先写已有条目和具体缺口。确需继续读大材料时，先在 state 的 next_action 指明尚未覆盖的验收条目，再只读该条目，不重新讨论路由。
4. 初稿写入 outputs/。测试用例默认列：场景、前置条件、操作步骤、预期结果、优先级、依据。其他文档按目标选择最小可检查结构。可以标注待确认项，但不能以个别细节为由延后整份初稿。
5. 每次补读前指出要确认**初稿中的哪条预期结果或事实缺口**；无法指出则停止扩展读取。默认不搭环境、不代跑、不全量审查、不检查发布；环境细节不是整理行为用例的前提。真正改变必过预期的缺口不能用猜测填补。
6. 当前工作区合并或冲突只记录为执行前提，继续以固定依据整理；仅当其改变纳入范围的预期结果时读取局部差异，不追踪操作人或连续扫描修改时间。
7. 达到 **20 次总工具调用**时必须收口判断：验收齐全则交付；仅可选细节缺失则说明后交付；必过事实缺失则保持非 done，交付已整理内容、具体阻塞与下一步。**必过项不能降为可选项**，部分初稿不能标为完成。原预算、无进展熔断仍适用；这些检查点**不是宿主自动拦截**。
8. 对照依据检查覆盖与事实，逐条检查步骤/预期/依据是否清楚；证据分别记入 evidence/coverage.txt 与 evidence/clarity.txt。关键词命中只算静态检查，不能替代内容核对。调用两个校验脚本后交付，明确「用例已整理，测试未执行」。若用户要求实际执行，单独进入执行流程并确认范围，不在文档任务中偷跑。

## 实施计划分支

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh <task-dir>` before broad exploration. For an existing task, read its contract and state first. If a model request times out, record a recovery summary in `audit/` before continuing.
2. Copy the approved `objective`、`done_when`、`scope`、`forbidden`、`risk` and decision gates; do not broaden scope.
3. If the contract uses the v2 format, copy every numbered `Acceptance` condition and preserve its verification type and layer.
4. Split work into independently verifiable tasks. Each task names exact target files, allowed changes, required verification, expected evidence and fallback when blocked.
5. Mark every verification and subtask `required` or `optional`; optional items need a written skip reason.
6. Include the done gate, contract revision and circuit-breaker thresholds.
7. Write the implementation plan to `.work-docs/tasks/<task-id>/outputs/` and state the first executable action.
