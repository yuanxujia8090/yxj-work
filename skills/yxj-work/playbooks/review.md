# Review Playbook

1. Read the contract, change set, evidence and unverified items. For a new formal task, create the task skeleton and minimal contract before broad exploration. If a model request times out, record the recovery summary in `audit/` before continuing.
2. Run `skills/yxj-work/scripts/check-contract.sh <task-dir>` for a v2 contract before reviewing the change set.
3. Apply the contract's `review_policy`: low/auto uses automatic verification plus a delivery summary; medium/user-confirm adds an independent read-only review; high/full-review requires user confirmation and full review.
   For `review_policy: auto` + low-risk + read-only reviews, use **轻量 review**: keep contract, evidence, state and both check scripts; skip builds, tests and unrelated reference files unless an Acceptance condition requires them.
4. 先列断言，再按断言读取局部实现。Start with an assertion ledger: list the document/spec claims or Acceptance conditions, map each to implementation symbols, read only the relevant local code, and write evidence immediately. Do not dump multiple complete source files before identifying the claim they answer.
5. Review correctness, security boundaries, maintainability, completion-condition coverage and workflow file boundary.
6. Confirm each numbered `Acceptance` condition has the declared evidence type and layer; do not treat a manual, consumer or external condition as passed from a local command alone.
7. Classify findings as must-fix, consider, note or rejected; cite files and evidence.
8. State what was not reviewed.
9. Write the review result to the contract's `review_evidence` path under `.work-docs/tasks/<task-id>/`; the state must record matching `policy` and `status=passed` before `done`.
10. This playbook is read-only. Put the review in `.work-docs/tasks/<task-id>/outputs/` only when requested by the contract.
