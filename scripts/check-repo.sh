#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'check-repo: %s\n' "$1" >&2; exit 1; }
need() { [[ -e "$ROOT/$1" ]] || fail "missing $1"; }

need README.md
need docs/architecture.md
need docs/file-boundary.md
need scripts/runtime-skills.txt
need skills/yxj-work/SKILL.md
need skills/yxj-work-long/SKILL.md
need skills/yxj-work-handoff/SKILL.md
need scripts/check-repo.sh
need scripts/install.sh
need scripts/check-workflow.sh
need scripts/check-state.sh
need scripts/test-install.sh
need scripts/test-fixtures.sh
need .work-docs/index.md
need .work-docs/tasks/20260928-01-yxj-work-independent-workflow/DECISIONS.md
need .work-docs/tasks/20260928-01-yxj-work-independent-workflow/evidence/old-skills.sha256

for file in "$ROOT"/skills/yxj-work/SKILL.md "$ROOT"/skills/yxj-work-long/SKILL.md "$ROOT"/skills/yxj-work-handoff/SKILL.md "$ROOT"/skills/yxj-work/playbooks/*.md; do
  [[ -f "$file" ]] || fail "missing runtime file $file"
done

# Every listed runtime skill must exist; the list is the single source of truth for install.sh.
while IFS= read -r skill; do
  [[ -f "$ROOT/skills/$skill/SKILL.md" ]] || fail "runtime-skills.txt lists missing skill: $skill"
done < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt")

# The English marker is checked separately below; the Chinese/English skills use the numeric marker.
for marker in 'name: yxj-work' 'name: yxj-work-long' 'name: yxj-work-handoff' '.work-docs' 'status: done' 'blocked_by' 'attempted_paths' 'unblock_condition' 'next_action' 'external_skill_write_outside_work_docs' '连续 3 次' '20 次工具调用' '30 次工具调用' '60 次工具调用' '30 分钟' 'calls_since_progress' 'last_progress_at' 'budget' 'strategy_fingerprints' 'evidence freshness' 'index.md' 'source=' 'static'; do
  grep -R -F -- "$marker" "$ROOT/skills" >/dev/null || fail "missing marker: $marker"
done

work_thresholds="$(grep -Eo 'L1/L2[^。]*20 次工具调用|L3 和 long 模式[^。]*60 次工具调用' "$ROOT/skills/yxj-work/SKILL.md" | tr '\n' ';')"
long_thresholds="$(grep -Eo '60 次工具调用或 30 分钟' "$ROOT/skills/yxj-work-long/SKILL.md" | tr '\n' ';')"
[[ "$work_thresholds" == *'20 次工具调用'* && "$work_thresholds" == *'60 次工具调用'* ]] || fail 'yxj-work thresholds missing'
[[ "$long_thresholds" == *'60 次工具调用或 30 分钟'* ]] || fail 'yxj-work-long thresholds missing'

# Runtime files may mention old names only in explicit protection/reference text.
if grep -R -n -E '(^|[^[:alnum:]_-])\.audit/|docs/handoff/|external local://|00-Inbox/|projects/<project>/docs/' "$ROOT/skills"; then
  fail 'forbidden external route in runtime skill'
fi
if grep -R -n -E '~/.pi/agent/skills/yxj-mode|yxj-mode-long/SKILL|yxj-handoff/SKILL' "$ROOT/skills"; then
  fail 'old skill runtime dependency found'
fi

printf 'check-repo: passed\n'
