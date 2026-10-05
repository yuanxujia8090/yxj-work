# Execute Playbook

1. Read contract, plan, state, target files, callers, tests, current differences, and the workspace baseline (cwd, branch/worktree, pending changes).
2. If the contract uses v2 format, run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before editing; do not execute against an incomplete contract.
3. List the current logical change and its required verification before editing.
4. Modify only files inside the task boundary. User project files are targets; workflow records stay in `.work-docs`.
5. Verify from narrow to broad: `syntax/config`, `static`, `runtime/local`, `external`, `consumer` as required by the contract. A manual, consumer or external condition must be explicitly recorded rather than silently treated as automatic.
6. If a contract condition changes, increase `contract_revision`, record old/new value, reason, approver and affected evidence before continuing.
7. After a failed verification, record the strategy fingerprint and use a materially different strategy. Three consecutive required failures trip the circuit breaker.
8. Preserve real output in `evidence/`; decisions and checkpoints go to `audit/`.
9. Apply the done gate. Never infer completion from exit code, build success, file existence or agent report alone.
