task_id: fixture-valid-blocked
level: L2
stage: blocked
status: blocked
done_when: dependency returns
calls_since_progress: 21
last_progress_at: 2026-09-28T18:00:00Z
budget: 22/100
strategy_fingerprints: scripts/check-state.sh + blocked fixture + missing dependency
blocked_by: missing dependency
unblock_condition: dependency is available
next_action: rerun required verification
required_verification: check-state status=blocked evidence=evidence/check.txt
evidence:check|command=printf blocked|run_at=2026-09-28T20:00:00Z|result=blocked|last_edit_at=2026-09-28T19:00:00Z
updated_at: 2026-09-28
