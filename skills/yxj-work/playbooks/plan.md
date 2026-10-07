# Plan Playbook

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before broad exploration. For an existing task, read its contract and state first. If a model request times out, record a recovery summary in `audit/` before continuing.
2. Copy the approved `objective`、`done_when`、`scope`、`forbidden`、`risk` and decision gates; do not broaden scope.
3. If the contract uses the v2 format, copy every numbered `Acceptance` condition and preserve its verification type and layer.
4. Split work into independently verifiable tasks. Each task names exact target files, allowed changes, required verification, expected evidence and fallback when blocked.
5. Mark every verification and subtask `required` or `optional`; optional items need a written skip reason.
6. Include the done gate, contract revision and circuit-breaker thresholds.
7. Write the implementation plan to `.work-docs/tasks/<task-id>/outputs/` and state the first executable action.
