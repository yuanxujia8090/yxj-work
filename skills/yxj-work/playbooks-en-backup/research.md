# Research Playbook

1. Confirm object, terminology, version and environment; unresolved identity blocks conclusions.
2. Rewrite the request as a falsifiable question with done_when and stop_when; split into 1–5 claims.
3. Prefer official documentation/API, official repositories/releases, primary data or user statements, reproducible measurements, then secondary sources.
4. Keep an evidence ledger with `claim`, `source`, `date`, `fact_or_inference`, `confidence`, `reproducible`, `contradiction`, and `scope`.
5. Separate facts, inferences and unknowns. Record failed paths and why they do not prove the claim.
6. Run a minimal measurement only when it can change the decision. Distinguish structure/configuration success from credential, permission, rate-limit and external-service failure.
7. Write the final report to `.work-docs/tasks/<task-id>/outputs/`; write ledger and run records to `evidence/` or `audit/`.
8. End with `decision_gate: proceed|design_only|gather_more|do_not_build` and a development handoff containing scope, evidence pointers, acceptance direction and irreversible decisions still requiring a human.
