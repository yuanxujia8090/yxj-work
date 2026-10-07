task_id: fixture-risk-policy-conflict
level: L2
task_type: exec
objective: 中风险任务错误自动放行
scope: shared/
forbidden: production/
risk: medium
risk_reason: 影响共享流程
review_policy: auto
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: 流程通过
verification: 运行测试
verification_type: automatic
layer: runtime/local
required: yes

## Decision Gates
confirmation: required
confirmation_status: pending
review: auto

## Contract Changes
- none
