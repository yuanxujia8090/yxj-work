# Review Playbook

1. Read the contract, change set, evidence and unverified items.
2. Run `skills/yxj-work/scripts/check-contract.sh <task-dir>` for a v2 contract before reviewing the change set.
3. Apply the contract's `review_policy`: low/auto uses automatic verification plus a delivery summary; medium/user-confirm adds an independent read-only review; high/full-review requires user confirmation and full review.
4. Review correctness, security boundaries, maintainability, completion-condition coverage and workflow file boundary.
5. Confirm each numbered `Acceptance` condition has the declared evidence type and layer; do not treat a manual, consumer or external condition as passed from a local command alone.
6. Classify findings as must-fix, consider, note or rejected; cite files and evidence.
7. State what was not reviewed.
8. Write the review result to the contract's `review_evidence` path under `.work-docs/tasks/<task-id>/`; the state must record matching `policy` and `status=passed` before `done`.
9. This playbook is read-only. Put the review in `.work-docs/tasks/<task-id>/outputs/` only when requested by the contract.
