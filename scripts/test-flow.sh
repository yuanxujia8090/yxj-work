#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-flow: %s\n' "$1" >&2; exit 1; }
need_text() {
  local file="$1" pattern="$2"
  grep -Fq -- "$pattern" "$ROOT/$file" || fail "missing '$pattern' in $file"
}

# Each common task shape must expose a complete route, not only a stage name.
need_text skills/yxj-work/SKILL.md '开发：`design → plan → exec → review`'
need_text skills/yxj-work/SKILL.md '问题排查与修复：`investigate → bugfix → review`'
need_text skills/yxj-work/SKILL.md '调研：`research → decision gate`'
need_text skills/yxj-work/SKILL.md '| exec | `playbooks/exec.md` |'
need_text skills/yxj-work/SKILL.md '| bugfix | `playbooks/bugfix.md` |'
need_text skills/yxj-work/SKILL.md '| research | `playbooks/research.md` |'

# Development keeps design, plan, execution and review as separate verifiable units.
need_text skills/yxj-work/playbooks/design.md 'Acceptance'
need_text skills/yxj-work/playbooks/design.md 'check-contract.sh'
need_text skills/yxj-work/playbooks/plan.md 'Acceptance'
need_text skills/yxj-work/playbooks/exec.md 'contract_revision'
need_text skills/yxj-work/playbooks/review.md 'review_policy'
need_text skills/yxj-work/SKILL.md '正式阶段先建任务骨架'
need_text skills/yxj-work/SKILL.md '断言驱动读取'
need_text skills/yxj-work/SKILL.md '超时恢复'
need_text skills/yxj-work/SKILL.md '固定收尾顺序'
need_text skills/yxj-work/playbooks/review.md '轻量 review'
need_text skills/yxj-work/playbooks/review.md '先列断言，再按断言读取局部实现'
need_text skills/yxj-work/playbooks/investigate.md 'create the task skeleton and minimal contract'
need_text skills/yxj-work/playbooks/research.md 'create the task skeleton and minimal contract'
need_text skills/yxj-work/playbooks/plan.md 'create the task skeleton and minimal contract'
need_text skills/yxj-work/playbooks/exec.md 'create the task skeleton and minimal contract'
need_text skills/yxj-work/playbooks/plan.md 'Split work into independently verifiable tasks'
need_text skills/yxj-work/playbooks/exec.md 'Verify from narrow to broad'
need_text skills/yxj-work/playbooks/review.md 'Review correctness, security boundaries'

# Bug fixing cannot skip reproduction or lose the before/after proof.
need_text skills/yxj-work/playbooks/bugfix.md 'Reproduce with expected versus actual behavior'
need_text skills/yxj-work/playbooks/bugfix.md 'Preserve failing-before and passing-after evidence'

# Research must separate facts from inference and stop at its decision gate.
need_text skills/yxj-work/playbooks/research.md 'Keep an evidence ledger'
need_text skills/yxj-work/playbooks/research.md 'End with `decision_gate: proceed|design_only|gather_more|do_not_build`'

# A long run must leave a next-session-readable record before it pauses or crosses a day.
need_text skills/yxj-work-long/SKILL.md '每个阶段结束都要追加一个 `audit/checkpoint-<序号>.md`'
need_text skills/yxj-work-long/SKILL.md '并同步更新 `state.md`'
need_text skills/yxj-work-long/SKILL.md '启动已有任务时，不创建新任务目录。先依次读取 `.work-docs/index.md`'
need_text skills/yxj-work-long/SKILL.md '`handoff.md`'
need_text skills/yxj-work-handoff/SKILL.md '下一会话第一步'

# show-me-your-work is intentionally not another runtime entry.
if grep -Fxq 'show-me-your-work' "$ROOT/scripts/runtime-skills.txt"; then
  fail 'show-me-your-work must not be a second long-run entry'
fi

printf 'test-flow: passed\n'
