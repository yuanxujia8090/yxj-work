task_id: fixture-high-risk-exempted
level: L3
task_type: ops
objective: 高风险任务错误豁免确认
scope: production/
forbidden: 未授权删除
risk: high
risk_reason: 生产变更
review_policy: full-review
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: 生产变更完成
verification: 运行生产检查
verification_type: external
layer: external
required: yes

## Decision Gates
confirmation: exempted
confirmation_reason: 夜间无人值守
review: full-review

## Contract Changes
- none
