#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'check-repo: %s\n' "$1" >&2; exit 1; }
need() { [[ -e "$ROOT/$1" ]] || fail "missing $1"; }

need README.md
need docs/architecture.md
need docs/file-boundary.md
need scripts/runtime-skills.txt
need skills/x-rail/SKILL.md
need skills/x-rail-long/SKILL.md
need skills/x-handoff/SKILL.md
need scripts/check-repo.sh
need scripts/install.sh
need scripts/check-workflow.sh
need skills/x-rail/scripts/check-state.sh
need skills/x-rail/scripts/check-contract.sh
need scripts/test-install.sh
need scripts/test-fixtures.sh
need scripts/test-v2-lifecycle.sh
need scripts/check-skill-metadata.sh
need scripts/test-skill-metadata.sh
need tests/fixtures/v2-review-valid/contract.md
need tests/fixtures/v2-review-valid/state.md
need scripts/test-flow.sh
need .work-docs/index.md

for file in "$ROOT"/skills/x-rail/SKILL.md "$ROOT"/skills/x-rail-long/SKILL.md "$ROOT"/skills/x-handoff/SKILL.md "$ROOT"/skills/x-rail/playbooks/*.md; do
  [[ -f "$file" ]] || fail "missing runtime file $file"
done
bash "$ROOT/scripts/check-skill-metadata.sh" "$ROOT" >/dev/null

# Every listed runtime skill must exist; the list is the single source of truth for install.sh.
while IFS= read -r skill; do
  [[ -f "$ROOT/skills/$skill/SKILL.md" ]] || fail "runtime-skills.txt lists missing skill: $skill"
done < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt")

# The English marker is checked separately below; the Chinese/English skills use the numeric marker.
for marker in 'name: x-rail' 'name: x-rail-long' 'name: x-handoff' '.work-docs' 'status: done' 'blocked_by' 'attempted_paths' 'unblock_condition' 'next_action' 'external_skill_write_outside_work_docs' '20 次工具调用' '60 次工具调用' '30 分钟' 'calls_since_progress' 'last_progress_at' 'budget' 'strategy_fingerprints' 'evidence freshness' 'static' '只能由用户主动调用' '自动扫描、推荐、注入' '替用户触发' 'disable-model-invocation' '参考技能' 'Acceptance' 'risk_reason' 'review_policy' 'contract_revision' 'verification_type' 'check-contract.sh'; do
  grep -R -F -- "$marker" "$ROOT/skills" >/dev/null || fail "missing marker: $marker"
done

work_thresholds="$(grep -Eo 'L1/L2[^。]*20 次工具调用|L3 和 long 模式[^。]*60 次工具调用|L1/L2/L3 的预算分别为 60/150/400 次工具调用' "$ROOT/skills/x-rail/SKILL.md" | tr '\n' ';')"
long_thresholds="$(grep -Eo '60 次工具调用或 30 分钟' "$ROOT/skills/x-rail-long/SKILL.md" | tr '\n' ';')"
[[ "$work_thresholds" == *'20 次工具调用'* && "$work_thresholds" == *'60 次工具调用'* && "$work_thresholds" == *'60/150/400 次工具调用'* ]] || fail 'x-rail thresholds missing'
[[ "$long_thresholds" == *'60 次工具调用或 30 分钟'* ]] || fail 'x-rail-long thresholds missing'

# Runtime files may mention old names only in explicit protection/reference text.
if grep -R -n -E '(^|[^[:alnum:]_-])\.audit/|docs/handoff/|external local://|00-Inbox/|projects/<project>/docs/' "$ROOT/skills"; then
  fail 'forbidden external route in runtime skill'
fi
if grep -R -n -E '~/.pi/agent/skills/yxj-mode|yxj-mode-long/SKILL|yxj-handoff/SKILL|~/.pi/agent/skills/yxj-work|yxj-work/SKILL|yxj-work-long/SKILL|yxj-work-handoff/SKILL' "$ROOT/skills"; then
  fail 'old skill runtime dependency found'
fi

# Cross-document consistency: a rule value must appear wherever the docs promise it.
# Budget numbers, the check-state path, and the status enum are asserted against every
# doc that states them, so editing one side without the other fails the repo check.
for doc in README.md docs/architecture.md docs/usage-guide.html; do
  grep -Fq '60/150/400' "$ROOT/$doc" || fail "budget numbers missing in $doc"
  grep -Fq 'skills/x-rail/scripts/' "$ROOT/$doc" || fail "check-state path missing in $doc"
done
grep -Fq '60/150/400 次工具调用' "$ROOT/skills/x-rail/SKILL.md" || fail 'budget numbers missing in x-rail SKILL.md'
grep -Fq 'in_progress|done|blocked|stopped|cancelled' "$ROOT/skills/x-rail/SKILL.md" || fail 'status enum missing in SKILL.md'
grep -Fq 'in_progress|done|blocked|stopped|cancelled' "$ROOT/skills/x-rail/scripts/check-state.sh" || fail 'status enum missing in check-state.sh'

# The stage enum in check-state.sh must be exactly the route names in SKILL.md plus `handoff`.
route_stages="$(awk '/^## 路由$/{f=1;next} /^## /{f=0} f' "$ROOT/skills/x-rail/SKILL.md" | sed -n 's/^- `\([a-z-]*\)`.*/\1/p' | sort | tr '\n' ' ')"
case_stages="$(sed -n 's/^  \(fast-answer|[a-z|-]*\)) ;;$/\1/p' "$ROOT/skills/x-rail/scripts/check-state.sh" | tr '|' '\n' | sort | tr '\n' ' ')"
expected_stages="$(printf '%s\n' $route_stages handoff | sort | tr '\n' ' ')"
[[ "$case_stages" == "$expected_stages" ]] || fail "stage enum mismatch: check-state.sh has [$case_stages], SKILL.md route + handoff gives [$expected_stages]"

printf 'check-repo: passed\n'
