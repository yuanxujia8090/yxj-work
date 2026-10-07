# Design Playbook

1. For a new formal task, create the task skeleton and minimal contract before broad exploration, then run `skills/yxj-work/scripts/check-contract.sh <task-dir>`. For an existing task, read the relevant code, task contract and research evidence first. Use assertion-driven local reads rather than dumping complete source files.
2. Describe the current chain, reusable capability, boundaries, assumptions and alternatives.
3. Define `objective`、`scope`、`forbidden`、`risk`、`risk_reason`、`review_policy` and numbered `Acceptance` conditions; each condition must include `outcome`、`verification`、`verification_type`、`layer` and `required`.
4. Keep `done_when` as a human-readable summary, then run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before moving to plan or exec.
5. For medium/high risk, record the confirmation decision in `Decision Gates`; do not treat L1/L2/L3 as a risk substitute.
6. Write the design to `.work-docs/tasks/<task-id>/outputs/`.
7. Do not modify project code in the design phase.
8. If research evidence is insufficient, stop at `design_only` or `gather_more`; do not create an execution task.
