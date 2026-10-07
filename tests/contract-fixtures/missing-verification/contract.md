task_id: fixture-missing-verification
level: L1
task_type: design
objective: 验收条件缺少验证方式
scope: plans/
forbidden: code/
risk: low
risk_reason: 文档任务
review_policy: auto
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: 文档存在
verification_type: automatic
layer: static
required: yes

## Decision Gates
confirmation: exempted
confirmation_reason: low risk
review: auto

## Contract Changes
- none
