task_id: fixture-valid-high
level: L3
task_type: ops
objective: 更新外部服务配置并验证生产行为
scope: 指定配置文件和验证记录
forbidden: 未授权的数据删除
risk: high
risk_reason: 涉及外部服务和生产行为
review_policy: full-review
contract_revision: 1
done_when: A1 通过

## Acceptance

### A1
outcome: 外部服务配置生效且无回归
verification: 运行外部环境验证清单
verification_type: external
layer: external
required: yes

## Unknowns

- none

## Decision Gates

confirmation: required
confirmation_status: confirmed
confirmation_by: user
confirmation_at: 2026-10-05T10:00+08:00
confirmation_source: user
review: full-review

## Contract Changes

- none
