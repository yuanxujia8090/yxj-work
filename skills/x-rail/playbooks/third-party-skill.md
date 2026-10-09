# Third-party Skill Boundary

1. Classify the skill as read-only, configurable-output, or fixed/unknown-write.
2. Read-only skills may run; record their result in task evidence.
3. Configurable-output skills must receive the exact allowed `.work-docs/tasks/<task-id>/outputs|evidence|tmp` path.
4. Fixed/unknown-write skills must not run in the real execution directory. Use an isolated disposable fixture or block the task.
5. Save before/after file inventories. Any unexpected path outside `.work-docs` trips the circuit breaker with `blocked_by: external_skill_write_outside_work_docs`.
6. Do not move, delete or overwrite an unexpected file without authorization.
