# Ops Playbook

## 阶段入口

适用场景：需要整理平台操作、账户配置、凭据设置、部署切换或其他由人完成的步骤。
输入：平台、账户/项目、操作目标、当前配置、回滚条件和允许范围。
输出：操作者清单、导航路径、精确字段值、预期确认和回滚说明。
不做什么：不代点网页，不执行不可逆平台操作，不把生产切换、费用或公开发布自动放行。
停止条件：手册可供人逐步执行，或关键外部事实不足而标记 blocked / stopped。

1. Produce an operator checklist; do not perform irreversible platform actions.
2. Record platform, account/project, navigation path, exact field value, expected confirmation and rollback.
3. Production switch, spending, public publishing, destructive changes and irreversible schema decisions set `status: stopped` pending user action.
4. Store manuals in `outputs/` and user-returned screenshots or command evidence in `evidence/`.
5. External failure is `blocked`, not success; distinguish configuration, credentials, permissions, rate limits and service health.
