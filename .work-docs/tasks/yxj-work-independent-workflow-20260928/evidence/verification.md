# Verification Evidence

## Historical / stale

以下结果来自最后一次 `scripts/install.sh` 改动之前，仅作历史参考，不能单独支撑交付：

- `bash scripts/check-repo.sh` → `check-repo: passed`
- `bash scripts/install.sh --dest <tmp>` → 临时安装成功
- `bash scripts/check-workflow.sh --source "$PWD" --installed <tmp>` → `check-workflow: passed`
- 旧路由与熔断 fixture → 历史输出为 passed，但旧 fixture 不在当前 required 清单中。

## Fresh required verification

原始完整输出：`evidence/verification-run-20260928.txt`

- command: `for f in scripts/*.sh; do bash -n "$f"; done`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `passed`
  - last_edit_at: `2026-09-28T11:21:56Z`（相关脚本与 skill 最晚编辑时间）
  - layer: `syntax/config`
- command: `bash scripts/check-repo.sh`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `passed`
  - last_edit_at: `2026-09-28T11:22:57Z`
  - layer: `static`
- command: `bash scripts/test-install.sh`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `test-install: passed`
  - last_edit_at: `2026-09-28T11:16:48Z`
  - layer: `runtime/local`
- command: `bash scripts/test-fixtures.sh`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `fixtures: passed`
  - last_edit_at: `2026-09-28T11:06:20Z`
  - layer: `runtime/local`
- command: `bash scripts/install.sh --dest <temporary-dir>` + `bash scripts/check-workflow.sh --source "$PWD" --installed <temporary-dir>`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `install: installed ...` and `check-workflow: passed`
  - last_edit_at: `2026-09-28T11:22:57Z`
  - layer: `runtime/local`
- command: `bash scripts/check-state.sh .work-docs/tasks/yxj-work-independent-workflow-20260928`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `check-state: passed`
  - last_edit_at: `2026-09-28T11:22:57Z`
  - layer: `static`
- command: `shasum -a 256 -c evidence/old-skills.sha256`
  - run_at: `2026-09-28T11:23:46Z`
  - result: `11/11 files: OK`
  - last_edit_at: `2026-09-28T11:19:00Z`（基线文件生成时间）
  - layer: `external`

## Scope notes

- 旧 `check-plan.sh` 未列为 required，仅保留为历史参考。
- 没有运行生产、外部网络或消费者集成验证；本任务契约不要求这些层级。
- `/tmp/yxj-work-old-skills-after.sha256` 没有任务开始前基线语义；当前 `evidence/old-skills.sha256` 是本轮建立的基线，并已与 `/tmp` 清单逐项核对。
