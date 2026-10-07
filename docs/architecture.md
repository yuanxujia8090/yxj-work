# Architecture

## Source and installation

`/Users/yuanxj/Documents/github/yxj-work` is the source of truth. Installed skills are copies or symlinks; the source repository remains the single source of truth. Runtime skills never import or read `yxj-mode`, `yxj-mode-long`, or `yxj-handoff`.

The repository owns three entry skills:

- `yxj-work`
- `yxj-work-long`
- `yxj-work-handoff`

It also carries 30 companion skills under `skills/yxj-*`, listed in `scripts/runtime-skills.txt` and installed alongside the entry skills. All of them set `disable-model-invocation: true`, so no task content auto-invokes them: an entry skill reads the file it needs on purpose (the stage → file table in `yxj-work/SKILL.md`), and the user may invoke one by name. Because entry and companion skills install into the same directory, the relative read path `../<name>/SKILL.md` holds in both the source repository and the install target.

## Runtime flow

新任务契约在执行前经过 `skills/yxj-work/scripts/check-contract.sh` 结构校验；它检查 `Acceptance`、`risk`、`review_policy`、`contract_revision` 等字段关系，要求字段从第 1 列写成 `key: value`（拒绝 `- key: value` 列表项），不做自然语言评分。历史契约没有 `Acceptance` 时保持 v1.x 兼容。

1. Classify the request as L0 fast-answer or L1/L2/L3 work.
2. For L1/L2/L3, resolve the current execution directory and initialize one `.work-docs` root.
3. Create or reuse a task directory named `{YYYYMMDD}-{NN}-{slug}` (format and number-allocation rule: `docs/file-boundary.md`); the `task_id` field equals that directory name.
4. Write the minimal contract before broad exploration; then run `skills/yxj-work/scripts/check-contract.sh <task-dir>`. Do not investigate for most of the task and add the contract at the end. New contracts use numbered `Acceptance` conditions, risk, review policy, decision gates and contract revision; `done_when` remains a compatibility summary.
5. After the contract passes, read the stage's playbook and companion skills in the table in `yxj-work/SKILL.md`, then use assertion-driven local reads and record evidence as it is produced.
6. If a model request times out, write a recovery summary to `audit/` before continuing; do not repeat the same request with the full history. When the host permits it, lower the thinking level or switch to a faster model without changing global Pi configuration.
7. Apply risk policy: medium-risk tasks need target/boundary confirmation and read-only review; high-risk tasks need user confirmation and full review. For low-risk, read-only, `review_policy: auto` reviews, use the lightweight path: retain contract, evidence, state and both check scripts, and skip unrelated builds/tests/reference reads. Verify required layers and apply the done gate; new state files bind `contract_revision`、`contract_fingerprint` and `required_verification` to the contract and Acceptance IDs. A done state must cover every required Acceptance condition; under `evidence_schema: 2` each one binds an evidence record, and medium/high-risk tasks also need a `review_evidence` line matching the contract's `review_policy`.
8. On failure or no progress, trip the child-task circuit breaker and persist a checkpoint.
9. For long work, update `state.md` and append a checkpoint at every stage boundary; before pausing or crossing a day, update `handoff.md` so the next session can print a recovery summary and execute `next_action` without chat memory.

## State model

`state.md` uses one `key: value` field per line. Required checks use `required_verification: <acceptance-id> status=... evidence=...` (the name is an Acceptance ID such as `A1`); evidence uses `evidence:name|acceptance=A1|command=...|run_at=...|result=...|last_edit_at=...`, and the referenced evidence file must exist. Tasks that opt into the current done gate add `evidence_schema: 2`; their `contract_revision` and `contract_fingerprint` must match the contract, and historical completed v2 states without `evidence_schema: 2` remain readable.

`check-state.sh` rejects a done task with failed/not_run/blocked required checks or stale evidence, rejects a non-blocked task at its no-progress threshold, and requires `blocked_by`, `unblock_condition`, and `next_action` for blocked tasks. With `evidence_schema: 2` it additionally requires every `required: yes` Acceptance to bind a complete evidence record (`acceptance`, `command`, `run_at`, `result=passed`, `last_edit_at`, file present), and for medium/high-risk tasks a `review_evidence` line whose `policy` matches the contract's `review_policy`, with `status=passed` and an existing review file. The script ships inside `skills/yxj-work/scripts/` and is installed with the skill, so run it against a task directory before writing `status: done`.

有效进展只包括新 evidence 或 required 验证变为 passed。L1/L2 无进展阈值为 20 次工具调用；L3/long 每个子任务为 60 次工具调用或 30 分钟。预算为 L1/L2/L3 分别 60/150/400 次工具调用；恢复时必须使用不同的策略指纹。关键词和 grep 检查只能作为 `static` 证据。

`in_progress -> done` is allowed only through the done gate. `in_progress -> blocked` is used for recoverable tool, evidence, dependency, or boundary failures. `in_progress -> stopped` is reserved for irreversible actions, user decisions, production changes, spending, publishing, or scope changes. `blocked -> in_progress` requires an unblocked dependency, a revalidated shared assumption, or an evidence-backed new strategy.

Parent tasks cannot be `done` while a required child is in_progress, blocked, stopped, or has failed/blocked/not_run required verification.
