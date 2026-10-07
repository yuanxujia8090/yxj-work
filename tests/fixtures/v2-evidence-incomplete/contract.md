task_id: 20260101-01-fixture-v2-evidence-incomplete
level: L1
task_type: exec
objective: 验证 v2 evidence 字段完整性
scope: fixture
forbidden: none
risk: low
risk_reason: 测试夹具
review_policy: auto
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: evidence 字段完整
verification: 运行 check-state.sh
verification_type: automatic
layer: static
required: yes

## Unknowns

- none

## Decision Gates
confirmation: exempted
confirmation_status: exempted
confirmation_by: system
confirmation_at: 2026-09-28T20:00:00Z
review: auto

## Contract Changes
- none
