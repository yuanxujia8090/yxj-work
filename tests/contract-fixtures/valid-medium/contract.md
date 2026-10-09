task_id: fixture-valid-medium
level: L2
task_type: exec
objective: 修改共享流程并保留原有行为
scope: skills/x-work/ 与对应测试
forbidden: 生产环境和用户目录
risk: medium
risk_reason: 影响公共工作流，但可以回滚
review_policy: user-confirm
contract_revision: 1
done_when: A1、A2 通过

## Acceptance

### A1
outcome: 共享流程按新规则运行
verification: 运行 scripts/test-flow.sh
verification_type: automatic
layer: runtime/local
required: yes

### A2
outcome: 用户确认目标和边界
verification: 用户在任务记录中确认
verification_type: manual
layer: consumer
required: yes

## Unknowns

- none

## Decision Gates

confirmation: required
confirmation_status: confirmed
confirmation_by: user
confirmation_at: 2026-10-05T10:00+08:00
confirmation_source: user
review: user-confirm

## Contract Changes

- none
