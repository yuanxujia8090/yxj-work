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

for skill in yxj-work yxj-work-long yxj-work-handoff; do
  [[ -d "$INSTALLED/$skill" ]] || fail "missing installed $skill"
  marker="$INSTALLED/$skill/.yxj-work-installed"
  [[ -f "$marker" ]] || fail "missing install marker for $skill"
  grep -Fqx "source=$SOURCE" "$marker" || fail "invalid install source for $skill"
done

# Compare all source files under skills. The marker is intentionally ignored.
while IFS= read -r -d '' src; do
  rel="${src#"$SOURCE/"}"
  [[ "$rel" == skills/* ]] || continue
  dst="$INSTALLED/${rel#skills/}"
  [[ -f "$dst" ]] || fail "missing installed file $rel"
  cmp -s "$src" "$dst" || fail "installed content differs: $rel"
done < <(find "$SOURCE/skills" -type f -print0)

# Installed runtime files must preserve the same boundary checks.
if grep -R -n -E '(^|[^[:alnum:]_-])\.audit/|docs/handoff/|external local://|00-Inbox/|projects/<project>/docs/' "$INSTALLED/yxj-work" "$INSTALLED/yxj-work-long" "$INSTALLED/yxj-work-handoff"; then
  fail 'forbidden external route in installed runtime skill'
fi
if grep -R -n -E '~/.pi/agent/skills/yxj-mode|yxj-mode-long/SKILL|yxj-handoff/SKILL' "$INSTALLED/yxj-work" "$INSTALLED/yxj-work-long" "$INSTALLED/yxj-work-handoff"; then
  fail 'old runtime dependency in installed skill'
fi

printf 'check-workflow: passed\n'
