# Execute Playbook

## 阶段入口

适用场景：已有通过校验的契约或实施计划，需要在允许范围内修改目标文件并完成验证。
输入：contract、state、实施计划、目标文件、调用方、测试和当前工作区基线。
输出：最小变更、真实验证输出、证据文件、未验证项和可交接状态。
不做什么：不超出契约范围，不用编译成功替代行为验证，不在失败后原样重复同一策略。
停止条件：required 验收和对应证据满足完成门，或遇到阻塞、越界、决策变化而停下并记录。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before broad exploration. For an existing task, read contract, plan, state, target files, callers, tests, current differences, and the workspace baseline (cwd, branch/worktree, pending changes). If a model request times out, record a recovery summary in `audit/` before continuing.
2. If the contract uses v2 format, run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before editing; do not execute against an incomplete contract.
3. List the current logical change and its required verification before editing. Read only the target symbols and their callers first; expand to full files only when a specific Acceptance condition requires it.
4. Modify only files inside the task boundary. User project files are targets; workflow records stay in `.work-docs`.
5. Verify from narrow to broad: `syntax/config`, `static`, `runtime/local`, `external`, `consumer` as required by the contract. A manual, consumer or external condition must be explicitly recorded rather than silently treated as automatic.
6. If a contract condition changes, increase `contract_revision`, record old/new value, reason, approver and affected evidence before continuing.
7. After a failed verification, record the strategy fingerprint and use a materially different strategy. Three consecutive required failures trip the circuit breaker.
8. Preserve real output in `evidence/`; decisions and checkpoints go to `audit/`.
9. Apply the done gate. Never infer completion from exit code, build success, file existence or agent report alone.
