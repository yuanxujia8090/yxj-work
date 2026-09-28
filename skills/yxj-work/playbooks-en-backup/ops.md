# Ops Playbook

1. Produce an operator checklist; do not perform irreversible platform actions.
2. Record platform, account/project, navigation path, exact field value, expected confirmation and rollback.
3. Production switch, spending, public publishing, destructive changes and irreversible schema decisions set `status: stopped` pending user action.
4. Store manuals in `outputs/` and user-returned screenshots or command evidence in `evidence/`.
5. External failure is `blocked`, not success; distinguish configuration, credentials, permissions, rate limits and service health.
