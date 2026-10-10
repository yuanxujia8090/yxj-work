# Execute Playbook

<stage name="exec">
  <inputs>当前用户授权、contract、state、当前阶段材料。明确只读时不落盘。输入与约束先核对。</inputs>
  <procedure>## 阶段入口

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
  <exit>输出新结论或目标产物版本、证据与未覆盖项。严格 check；候选完成走 task.py complete。阻塞保留状态，不放宽必需验收。</exit>
</stage>
