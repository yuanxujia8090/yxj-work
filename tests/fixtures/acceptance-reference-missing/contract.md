task_id: 20260101-01-fixture-contract-linked-valid
level: L1
stage: review
status: done
objective: 验证 state 与 contract 关联
scope: fixture
forbidden: none
risk: low
risk_reason: 测试夹具
review_policy: auto
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: state 可以引用 A1
verification: 运行 check-state.sh
verification_type: automatic
layer: static
required: yes

## Decision Gates
confirmation: exempted
confirmation_status: exempted
confirmation_by: system
confirmation_at: 2026-09-28T20:00:00Z
review: auto

## Contract Changes
- none
