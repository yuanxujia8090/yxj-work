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

command -v python3 >/dev/null || fail 'Python 3 is required'
need skills/x-rail/scripts/task.py
need skills/x-rail/scripts/task_checks.py
need skills/x-self-check/scripts/analyze_sessions.py
need scripts/check-skill-xml.py
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/scripts/check-skill-xml.py" --root "$ROOT" >/dev/null

# Runtime files may mention old names only in explicit protection/reference text.
if grep -R -n -E '(^|[^[:alnum:]_-])\.audit/|docs/handoff/|external local://|00-Inbox/|projects/<project>/docs/' "$ROOT/skills"; then
  fail 'forbidden external route in runtime skill'
fi
if grep -R -n -E '~/.pi/agent/skills/yxj-[a-z0-9-]+|yxj-[a-z0-9-]+/SKILL' "$ROOT/skills"; then
  fail 'old skill runtime dependency found'
fi

# Cross-document consistency: a rule value must appear wherever the docs promise it.
# Budget numbers, the check-state path, and the status enum are asserted against every
# doc that states them, so editing one side without the other fails the repo check.
for doc in README.md docs/architecture.md docs/usage-guide.html; do
  grep -Fq '60/150/400' "$ROOT/$doc" || fail "budget numbers missing in $doc"
  grep -Fq 'skills/x-rail/scripts/' "$ROOT/$doc" || fail "check-state path missing in $doc"
done
# XML checker compares the canonical routes with the shared Python stage enum.
# Budget values are attributes, not fragile translated prose.
PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'skills/x-rail/scripts'))
import task_checks
assert task_checks.STATUSES == {'in_progress','done','blocked','stopped','cancelled'}
PY

printf 'check-repo: passed\n'
