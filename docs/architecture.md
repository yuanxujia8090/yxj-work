# Architecture

## Source and installation

`/Users/yuanxj/Documents/github/yxj-work` is the source of truth. The Pi skill directory contains installed copies only. Runtime skills never import or read `yxj-mode`, `yxj-mode-long`, or `yxj-handoff`.

The repository owns three namespaced skills:

- `yxj-work`
- `yxj-work-long`
- `yxj-work-handoff`

Generic Pi skills remain external dependencies. They are not copied or renamed merely because a workflow invokes them.

## Runtime flow

1. Classify the request as L0 fast-answer or L1/L2/L3 work.
2. For L1/L2/L3, resolve the current execution directory and initialize one `.work-docs` root.
3. Create or reuse a task directory keyed by `task_id`.
4. Write contract/state before durable work.
5. Run the selected playbook and record evidence.
6. Verify required layers and apply the done gate.
7. On failure or no progress, trip the child-task circuit breaker and persist a checkpoint.

## State model

`state.md` uses one `key: value` field per line. Required checks use `required_verification: name status=... evidence=...`; evidence uses `evidence:name|command=...|run_at=...|result=...|last_edit_at=...`. `check-state.sh` rejects a done task with failed/not_run/blocked required checks or stale evidence, rejects a non-blocked task at its no-progress threshold, and requires `blocked_by`, `unblock_condition`, and `next_action` for blocked tasks.

有效进展只包括新 evidence 或 required 验证变为 passed。L1/L2 无进展阈值为 20 次工具调用；L3/long 每个子任务为 60 次工具调用或 30 分钟。预算为 L1/L2/L3 分别 30/100/400 次工具调用；恢复时必须使用不同的策略指纹。关键词和 grep 检查只能作为 `static` 证据。

`pending -> active -> done` is allowed only through the done gate. `active -> blocked` is used for recoverable tool, evidence, dependency, or boundary failures. `active -> stopped` is reserved for irreversible actions, user decisions, production changes, spending, publishing, or scope changes. `blocked -> active` requires an unblocked dependency, a revalidated shared assumption, or an evidence-backed new strategy.

Parent tasks cannot be `done` while a required child is active, blocked, stopped, or has failed/blocked/not_run required verification.
