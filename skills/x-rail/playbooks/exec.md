# Execute Playbook

<stage name="exec">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；下面的 contract/state、初始化、evidence/audit 和候选要求只适用于严格记录。用户授权的目标文档写指定位置。

适用场景：已有通过校验的契约或实施计划，需要在允许范围内修改目标文件并完成验证。
输入：contract、state、实施计划、目标文件、调用方、测试和当前工作区基线。
输出：最小变更、真实验证输出、证据文件、未验证项和可交接状态。
不做什么：不超出契约范围，不用编译成功替代行为验证，不在失败后原样重复同一策略。
停止条件：required 验收和对应证据满足完成门，或遇到阻塞、越界、决策变化而停下并记录。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before broad exploration. For an existing task, read contract, plan, state, target files, callers, tests, current differences, and the workspace baseline (cwd, branch/worktree, pending changes). If a model request times out, record a recovery summary in `audit/` before continuing.
2. If the contract uses v2 format, run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before editing; do not execute against an incomplete contract.
3. List the current logical change and its required verification before editing. Read only the target symbols and their callers first; expand to full files only when a specific Acceptance condition requires it.
4. Modify only files inside the task boundary. User project files are targets; workflow records stay in `.work-docs`.
5. Verify from narrow to broad: `syntax/config`, `static`, `runtime/local`, `external`, `consumer` as required by the contract. A manual, consumer or external condition must be explicitly recorded rather than silently treated as automatic.
6. If a contract condition changes, increase `contract_revision`, record old/new value, reason, approver and affected evidence before continuing.
7. After a failed verification, record the strategy fingerprint and use a materially different strategy. Three consecutive required failures trip the circuit breaker.
8. Preserve real output in `evidence/`; decisions and checkpoints go to `audit/`.
9. Apply the done gate. Never infer completion from exit code, build success, file existence or agent report alone.</procedure>
  <quality_check>先失败反例后最小实现；共同变化逻辑只维护一处，接口保持小。项目规范优先，非 TypeScript 不注入专用规则。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
