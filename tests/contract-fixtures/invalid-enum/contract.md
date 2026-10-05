task_id: fixture-invalid-enum
level: L1
task_type: design
objective: 枚举非法
scope: plans/
forbidden: code/
risk: low
risk_reason: 文档任务
review_policy: human
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: 文档存在
verification: 检查文档
verification_type: robot
layer: static
required: maybe

## Decision Gates
confirmation: exempted
confirmation_reason: low risk
review: auto

## Contract Changes
- none
