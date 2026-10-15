# 长任务依赖和运行引用

适用：跨会话、外部等待、独立依赖汇总。普通多阶段本身不触发。先按主入口写完整契约、封存，再记录事实。不补造历史快照。

## 工作项清单与单一状态

复杂或大范围实施先拆工作项并持久记录，不按需求数量触发；拆分本身不等于长模式。普通局部任务仍可会话内清单，只读分析不落盘。新严格实施契约采用下例；start 对 task_type=exec|bugfix 强制 schema，mixed/ops 等其他类型不由脚本猜测是否实施，但触发复杂度或范围条件的严格实施仍须显式采用，不能换类型绕过。旧记录 check/update 兼容，需要清单时显式升级契约并保留快照，不自动迁移或补造历史。

```text
# contract.md 顶部；R1/R2 为需求，A1/A2/A3 须存在于实际 Acceptance
work_items_schema: 1
requirement:R1|outcome=服务端支持目标行为
requirement:R2|outcome=客户端可使用并展示该行为
work_item:W1|title=服务端实现|requirements=R1|depends=none|scope=src/service.py,tests/test_service.py|required=yes|acceptances=A1|skip_reason=none
work_item:W2|title=客户端实现|requirements=R2|depends=none|scope=src/client.ts,tests/client.test.ts|required=yes|acceptances=A2|skip_reason=none
work_item:W3|title=端到端集成|requirements=R1,R2|depends=W1,W2|scope=tests/integration.py|required=yes|acceptances=A3|skip_reason=none
```

W1/W2 只有共享接口已固定、资源隔离且当前授权允许时才可并行；否则在原状态/决定记录具体串行原因，不通过改依赖掩饰。主会话负责共享约定、集成与最终验收，父 state 唯一写入者。每项完成重查就绪项，不等待无关整批。子代理独立副本，数据库、缓存和构建目录同样分配所有权。

```text
# state.md 初始片段，由 start 初始化；实施细节计划只引用 W1/W2/W3
work_item_state:W1|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none|unblock_condition=none|reason=尚未开始|next_action=读取服务与测试
work_item_state:W2|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none|unblock_condition=none|reason=尚未开始|next_action=读取客户端与测试
work_item_state:W3|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none|unblock_condition=none|reason=尚未开始|next_action=待 W1 和 W2 验证后核对集成入口
active_work_items: none
```

用 update --item 和 --item-* 更新执行者、状态、原因与第一动作，完整参数见 ../playbooks/verification.md。七状态 pending/in_progress/awaiting_verification/needs_fix/blocked/verified/skipped 不混入整体 in_progress/done/blocked/stopped/cancelled。active_work_items 由 in_progress 项自动生成并校验一致；可选项 skipped 自动引用契约非空且非 none 的 skip_reason，保留本次 item-reason 动作说明。run/record 除原 required=yes 验收外，仅开放 schema=1 清单 work_item.acceptances 引用的 required=no 验收；未引用的可选验收仍拒绝，run 自动/record 非自动边界不变。不改变契约 required 语义，不自动升为整体必过；工作项 verified 仍须全部引用验收 passed 且证据有效，必需工作项不能 skipped，可选工作项合法 skipped 不制造 passed。工作项引用原验收及证据，不复制 passed；提交与子代理通知不能替代验收。某项受阻而其他可继续时不阻塞整体。

依赖修复不级联状态。例如 W3 已在做，前置 W1 证据过期时，可直接将 W1 退回待验证，无须先逐项阻塞后继；W3 保留真实既有状态，不自动级联修改。启动或重新激活后继、进入 verified 及 finish/complete 时，仍检查前置已验证且证据当前有效。summary 只读标过期事实，不能沿用旧状态放行完成；静态定义继续校验引用和无环，不新增级联状态机。

开始、实现完成、验证、审查返回、阻塞/解除、重要阶段变化、提交、压缩和交接前核对相关项。真实新结论才声明 --progress；整体 next_action 只放第一可执行动作，完成候选为交付/结束说明。handoff 只补恢复第一步与易错点，引用原 state，不另建进度文件。

## 独立子任务与原运行

工作项只是同一目标内交付，不为每项新建 task-id。只有目标独立且需单独契约的子任务才登记下列 Dependencies；audit/runs.json 沿用真实子任务绑定，不另造调度状态。成本策略与授权传递到已授权子任务，硬限制和准确错误另记；容量未知不编百分比，模型请求超时不等于工具超时。

父契约示例：

```text
## Dependencies
dependency: child-review|task_id=20261010-03-review|required=yes|acceptance=A2
dependency: optional-reference|task_id=20261010-04-reference|required=no|acceptance=A3|skip_reason=本次固定材料足够，不依赖新资料
```

依赖验收编号属于父契约。子任务结束不自动通过父验收。完成入口递归检查子契约、快照、状态、证据，拒绝循环、重复、自引用、目录逃逸和未完成必需项。

运行引用保存到 audit/runs.json，内容为真实工具返回值。下面仅为结构示例，不能作为完成证据：

```json
{
  "version": 1,
  "runs": [{
    "key": "child-review",
    "provider": "pi-subagents",
    "run_id": "实际运行标识",
    "task_id": "20261010-03-review",
    "workspace": "/absolute/isolated/worktree",
    "observed_status": "running",
    "observed_at": "2026-10-10T02:00:00Z",
    "output_reference": null
  }]
}
```

运行记录 key 与 task_id 必须对应已封存依赖。observed_status 使用 unknown、queued、pending、running、waiting、needs_attention、completed、done、failed、blocked、stopped、cancelled、interrupted、timed_out 中的真实观察值；无法映射先写 unknown，不把完成观察当成父验收通过。

恢复读取索引 → contract → state → 最近 checkpoint → handoff → runs → 相关 evidence；核对工作区、提交、未提交差异和输入摘要。原运行已结束就核对原产物，不重发。原运行不可查就记 unknown/blocked，等待恢复能力。handoff 不能扩大授权。阶段、提交、会话或工作项变化不更换原任务编号。基础设施故障立即报告并暂停该依赖，保留原运行、准确错误和产物，不换协议或前后台。派发后有独立工作继续，无独立工作交还控制权等原生通知；仅在依赖处汇总。审查集中返回必修问题，集中修复后优先恢复原审查运行复核，不替代契约要求的独立最终审查。
