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
5. Concurrency: two sessions may allocate the same number. After appending the index line, re-read `tasks/` and `index.md`; if the number is taken, keep the first task, move the later one to the next free number, and record the conflict in `audit/`.

The `task_id` field in `contract.md` and `state.md` equals the full directory name, so the task stays locatable from its own records.

- `outputs/`: final reports, designs, plans, manuals.
- `evidence/`: command output, source pointers, reproducible measurements, failure evidence.
- `audit/`: decisions, checkpoints, work-in-progress and failure records.
- `tmp/`: reusable fixtures and disposable verification material.

明确只读分析时不创建任务文件，直接在回复交付。需要持久任务记录时，新任务均有 contract.md、state.md 和封存快照；evidence/、outputs/、tmp/ 按需创建。新任务前先读 `.work-docs/index.md`，范围相同且仍在进行时续用原 task id，不新建任务。

No workflow-generated durable file may go to `.audit/`, `docs/handoff/`, `00-Inbox/`, a project docs directory, external `local://`, or an external `.audit/`.

This file lives in the source repository and is not copied by `install.sh`. Runtime skills therefore inline the rules they need: the entry skills and the companion skill boundary sections carry the task-id format and allocation steps verbatim. Do not point a runtime skill at this path.

## Third-party skills

A third-party skill is either read-only, output-root configurable, or fixed/unknown-write. Only the first two can run in the real execution directory. Fixed/unknown-write skills run only in an isolated fixture after their write set is observed; otherwise the task is blocked.

Before and after invocation, record a file inventory. An unexpected path outside `.work-docs` is a boundary violation. Do not move or delete it without authorization.

## Contract validation and project code

新任务的 `contract.md` 必须在执行前通过 `skills/x-rail/scripts/check-contract.sh <task-dir>`。契约字段必须从第 1 列写成 `key: value`，写成 `- key: value` 列表项会被报 `fields must use key: value at column 1`。默认检查只读契约，不自动改验收标准；显式 seal 才保存快照。历史契约必须用 `--legacy-readonly`，不得据此提交新完成，也不批量迁移历史。严格检查不因缺少 Acceptance 自动降级。

契约中的 `Acceptance`、`Decision Gates` 和 `Contract Changes` 属于工作流记录，必须留在 `.work-docs/tasks/<task-id>/`。契约实质变化要提升 `contract_revision`，记录旧值、新值、原因、批准人和受影响证据。

User-specified project code is a task target, not a workflow artifact. Record its paths in the task contract and evidence, but do not copy it into `.work-docs` unless requested.
