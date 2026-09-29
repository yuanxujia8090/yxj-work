# Architecture

## Source and installation

`/Users/yuanxj/Documents/github/yxj-work` is the source of truth. Installed skills are copies or symlinks; the source repository remains the single source of truth. Runtime skills never import or read `yxj-mode`, `yxj-mode-long`, or `yxj-handoff`.

The repository owns three entry skills:

- `yxj-work`
- `yxj-work-long`
- `yxj-work-handoff`

It also carries 30 companion skills under `skills/yxj-*`, listed in `scripts/runtime-skills.txt` and installed alongside the entry skills. All of them set `disable-model-invocation: true`, so no task content auto-invokes them: an entry skill reads the file it needs on purpose (the stage → file table in `yxj-work/SKILL.md`), and the user may invoke one by name. Because entry and companion skills install into the same directory, the relative read path `../<name>/SKILL.md` holds in both the source repository and the install target.

## Runtime flow

1. Classify the request as L0 fast-answer or L1/L2/L3 work.
2. For L1/L2/L3, resolve the current execution directory and initialize one `.work-docs` root.
3. Create or reuse a task directory named `{YYYYMMDD}-{NN}-{slug}` (format and number-allocation rule: `docs/file-boundary.md`); the `task_id` field equals that directory name.
4. Write contract/state before durable work.
5. Read the stage's playbook first, then the companion skills in the stage table in `yxj-work/SKILL.md`; record the resulting files and evidence.
6. Verify required layers and apply the done gate.
7. On failure or no progress, trip the child-task circuit breaker and persist a checkpoint.
8. For long work, update `state.md` and append a checkpoint at every stage boundary; before pausing or crossing a day, update `handoff.md` so the next session can print a recovery summary and execute `next_action` without chat memory.

## State model

`state.md` uses one `key: value` field per line. Required checks use `required_verification: name status=... evidence=...`; evidence uses `evidence:name|command=...|run_at=...|result=...|last_edit_at=...`. `check-state.sh` rejects a done task with failed/not_run/blocked required checks or stale evidence, rejects a non-blocked task at its no-progress threshold, and requires `blocked_by`, `unblock_condition`, and `next_action` for blocked tasks. The script ships inside `skills/yxj-work/scripts/` and is installed with the skill, so run it against a task directory before writing `status: done`.

有效进展只包括新 evidence 或 required 验证变为 passed。L1/L2 无进展阈值为 20 次工具调用；L3/long 每个子任务为 60 次工具调用或 30 分钟。预算为 L1/L2/L3 分别 60/150/400 次工具调用；恢复时必须使用不同的策略指纹。关键词和 grep 检查只能作为 `static` 证据。

`in_progress -> done` is allowed only through the done gate. `in_progress -> blocked` is used for recoverable tool, evidence, dependency, or boundary failures. `in_progress -> stopped` is reserved for irreversible actions, user decisions, production changes, spending, publishing, or scope changes. `blocked -> in_progress` requires an unblocked dependency, a revalidated shared assumption, or an evidence-backed new strategy.

Parent tasks cannot be `done` while a required child is in_progress, blocked, stopped, or has failed/blocked/not_run required verification.
