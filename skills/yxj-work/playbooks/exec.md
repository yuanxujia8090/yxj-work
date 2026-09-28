# Execute Playbook

1. Read contract, plan, state, target files, callers, tests and current differences.
2. List the current logical change and its required verification before editing.
3. Modify only files inside the task boundary. User project files are targets; workflow records stay in `.work-docs`.
4. Verify from narrow to broad: `syntax/config`, `static`, `runtime/local`, `external`, `consumer` as required by the contract.
5. After a failed verification, record the strategy fingerprint and use a materially different strategy. Three consecutive required failures trip the circuit breaker.
6. Preserve real output in `evidence/`; decisions and checkpoints go to `audit/`.
7. Apply the done gate. Never infer completion from exit code, build success, file existence or agent report alone.
