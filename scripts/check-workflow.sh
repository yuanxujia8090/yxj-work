#!/usr/bin/env bash
set -euo pipefail

SOURCE=''
INSTALLED=''
usage() { printf 'usage: %s --source DIR --installed DIR\n' "$0"; }
while (($#)); do
  case "$1" in
    --source) (($# >= 2)) || { usage >&2; exit 2; }; SOURCE="$2"; shift 2 ;;
    --installed) (($# >= 2)) || { usage >&2; exit 2; }; INSTALLED="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ -n "$SOURCE" && -n "$INSTALLED" ]] || { usage >&2; exit 2; }
SOURCE="$(cd "$SOURCE" && pwd -P)"
INSTALLED="$(cd "$INSTALLED" && pwd -P)"
fail() { printf 'check-workflow: %s\n' "$1" >&2; exit 1; }

runtime_skills() { grep -vE '^[[:space:]]*(#|$)' "$SOURCE/scripts/runtime-skills.txt"; }

# Each runtime skill must exist in both trees. Symlink deployments must point at this
# source repository; copied deployments must carry a valid install marker.
while IFS= read -r skill; do
  dst="$INSTALLED/$skill"
  if [[ -L "$dst" ]]; then
    target="$(readlink "$dst")"
    case "$target" in
      /*) abs="$target" ;;
      *) abs="$(dirname "$dst")/$target" ;;
    esac
    resolved="$(cd "$abs" 2>/dev/null && pwd -P)" || fail "broken install link for $skill"
    expected="$(cd "$SOURCE/skills/$skill" 2>/dev/null && pwd -P)" || fail "missing source skill $skill"
    [[ "$resolved" == "$expected" ]] || fail "install link for $skill points to $resolved, expected $expected"
    continue
  fi
  [[ -d "$dst" ]] || fail "missing installed $skill"
  marker="$dst/.x-rail-installed"
  [[ -f "$marker" ]] || fail "missing install marker for $skill"
  grep -Fqx "source=$SOURCE" "$marker" || fail "invalid install source for $skill"
done < <(runtime_skills)

# Compare every runtime skill's source files. The marker is intentionally ignored.
# Non-runtime material under skills/ (see skills/README.md) is not installed, so it is not compared.
# Symlinked skills resolve back into the source repository, so there is nothing to compare.
while IFS= read -r skill; do
  [[ -L "$INSTALLED/$skill" ]] && continue
  while IFS= read -r -d '' src; do
    rel="${src#"$SOURCE/"}"
    dst="$INSTALLED/${rel#skills/}"
    [[ -f "$dst" ]] || fail "missing installed file $rel"
    cmp -s "$src" "$dst" || fail "installed content differs: $rel"
  done < <(find "$SOURCE/skills/$skill" -type f -print0)
done < <(runtime_skills)

# Reverse check: a copied skill must not contain files absent from the source tree.
while IFS= read -r skill; do
  [[ -L "$INSTALLED/$skill" ]] && continue
  while IFS= read -r -d '' inst; do
    rel="${inst#"$INSTALLED/"}"
    [[ -f "$SOURCE/skills/${rel}" ]] || fail "unexpected installed file: $rel"
  done < <(find "$INSTALLED/$skill" -type f ! -name '.x-rail-installed' -print0)
done < <(runtime_skills)

# The contract checker is part of the installed x-rail runtime.
[[ -f "$INSTALLED/x-rail/scripts/check-contract.sh" ]] || fail 'missing installed contract checker'

# Installed runtime files must preserve the same boundary checks.
# The trailing slash on each path matters: `grep -R dir` does not descend into a
# symlinked install directory (the --link deployment), so without it these two
# assertions exit 1 on an empty scan and silently pass.
# grep exit code: 0 = violation found, 1 = clean, >=2 = the check itself broke (never a pass).
rc=0
grep -R -n -E '(^|[^[:alnum:]_-])\.audit/|docs/handoff/|external local://|00-Inbox/|projects/<project>/docs/' "$INSTALLED/x-rail/" "$INSTALLED/x-rail-long/" "$INSTALLED/x-handoff/" || rc=$?
[[ "$rc" -le 1 ]] || fail "boundary grep failed (rc=$rc)"
[[ "$rc" -eq 1 ]] || fail 'forbidden external route in installed runtime skill'
rc=0
grep -R -n -E '~/.pi/agent/skills/yxj-mode|yxj-mode-long/SKILL|yxj-handoff/SKILL|~/.pi/agent/skills/yxj-work|yxj-work/SKILL|yxj-work-long/SKILL|yxj-work-handoff/SKILL' "$INSTALLED/x-rail/" "$INSTALLED/x-rail-long/" "$INSTALLED/x-handoff/" || rc=$?
[[ "$rc" -le 1 ]] || fail "old-name grep failed (rc=$rc)"
[[ "$rc" -eq 1 ]] || fail 'old runtime dependency in installed skill'

printf 'check-workflow: passed\n'
