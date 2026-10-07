task_id: fixture-duplicate-acceptance
level: L1
task_type: design
objective: 验收编号重复
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
verification: 检查文档
verification_type: automatic
layer: static
required: yes

### A1
outcome: 第二个结果
verification: 再次检查
verification_type: automatic
layer: static
required: yes

## Decision Gates
confirmation: exempted
confirmation_reason: low risk
review: auto

## Contract Changes
- none
