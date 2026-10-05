# Plan Playbook

1. Copy the approved `objective`、`done_when`、`scope`、`forbidden`、`risk` and decision gates; do not broaden scope.
2. If the contract uses the v2 format, copy every numbered `Acceptance` condition and preserve its verification type and layer.
3. Split work into independently verifiable tasks. Each task names exact target files, allowed changes, required verification, expected evidence and fallback when blocked.
4. Mark every verification and subtask `required` or `optional`; optional items need a written skip reason.
5. Include the done gate, contract revision and circuit-breaker thresholds.
6. Write the implementation plan to `.work-docs/tasks/<task-id>/outputs/` and state the first executable action.
