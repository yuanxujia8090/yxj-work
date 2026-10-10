# 长任务依赖和运行引用

适用：跨会话、外部等待、独立依赖汇总。普通多阶段本身不触发。先按主入口写完整契约、封存，再记录事实。不补造历史快照。

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

恢复读取索引 → contract → state → 最近 checkpoint → handoff → runs → 相关 evidence；核对工作区、提交、未提交差异和输入摘要。原运行已结束就核对原产物，不重发。原运行不可查就记 unknown/blocked，等待恢复能力。handoff 不能扩大授权。
