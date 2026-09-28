# File Boundary

## Allowed workflow files

For a task running in `<execution-root>`:

```text
<execution-root>/.work-docs/tasks/<task-id>/
├── contract.md
├── state.md
├── handoff.md
├── evidence/
├── outputs/
├── audit/
└── tmp/
```

## Task id format

`<task-id>` is the task directory name, never a bare slug:

```text
{YYYYMMDD}-{NN}-{slug}          e.g. 20260928-01-yxj-work-independent-workflow
```

- `{YYYYMMDD}`: local date when the task is first created.
- `{NN}`: two-digit counter, restarting at `01` each day. Per-day numbering keeps the next number
  discoverable by listing one day's directories, and keeps the counter at two digits as history grows.
- `{slug}`: short lowercase kebab-case task name.

Allocate the number before creating the directory:

1. Read `.work-docs/index.md`. If an in-progress task covers the same scope, reuse its id; do not allocate a new one.
2. Otherwise list `.work-docs/tasks/` and take the highest `{NN}` among directories starting with today's date, then add 1.
3. Never reuse or renumber the number of a task that was completed or removed.
4. Append the new task to `.work-docs/index.md`.

The `task_id` field in `contract.md` and `state.md` equals the full directory name, so the task stays locatable from its own records.

- `outputs/`: final reports, designs, plans, manuals.
- `evidence/`: command output, source pointers, reproducible measurements, failure evidence.
- `audit/`: decisions, checkpoints, work-in-progress and failure records.
- `tmp/`: reusable fixtures and disposable verification material.

L1 可以只创建 `tasks/<task-id>/state.md`，`evidence/`、`outputs/`、`audit/`、`tmp/` 按需创建；L2/L3 保持完整结构。新任务前先读 `.work-docs/index.md`，范围相同且仍在进行时续用原 task id，不新建任务。

No workflow-generated durable file may go to `.audit/`, `docs/handoff/`, `00-Inbox/`, a project docs directory, external `local://`, or an external `.audit/`.

## Third-party skills

A third-party skill is either read-only, output-root configurable, or fixed/unknown-write. Only the first two can run in the real execution directory. Fixed/unknown-write skills run only in an isolated fixture after their write set is observed; otherwise the task is blocked.

Before and after invocation, record a file inventory. An unexpected path outside `.work-docs` is a boundary violation. Do not move or delete it without authorization.

## Project code

User-specified project code is a task target, not a workflow artifact. Record its paths in the task contract and evidence, but do not copy it into `.work-docs` unless requested.
