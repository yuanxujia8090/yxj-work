#!/usr/bin/env bash
set -euo pipefail

TASK_DIR="${1:-}"
[[ -n "$TASK_DIR" && -f "$TASK_DIR/state.md" ]] || { printf 'check-state: usage: %s TASK_DIR\n' "$0" >&2; exit 2; }
fail() { printf 'check-state: %s\n' "$1" >&2; exit 1; }
value() { sed -n "s/^$1: //p" "$TASK_DIR/state.md" | head -n 1; }
status="$(value status)"
level="$(value level)"
calls="$(value calls_since_progress)"
budget="$(value budget)"
[[ -n "$status" ]] || fail 'missing status'
[[ "$calls" =~ ^[0-9]+$ ]] || fail 'invalid calls_since_progress'
case "$level" in
  L1|L2) threshold=20 ;;
  L3|long) threshold=60 ;;
  *) fail 'invalid level' ;;
esac
if (( calls >= threshold )) && [[ "$status" != blocked ]]; then
  fail "calls_since_progress reached $threshold while status is not blocked"
fi
if [[ "$budget" =~ ^([0-9]+)/([0-9]+)$ ]]; then
  used="${BASH_REMATCH[1]}"; limit="${BASH_REMATCH[2]}"
  if (( used >= limit )) && [[ "$status" == done ]]; then fail 'budget exhausted but status is done'; fi
else
  fail 'invalid budget; expected used/limit'
fi
if [[ "$status" == blocked ]]; then
  for key in blocked_by unblock_condition next_action; do
    [[ -n "$(value "$key")" ]] || fail "blocked state missing $key"
  done
fi
while IFS= read -r line; do
  [[ "$line" == required_verification:* ]] || continue
  req_status="${line##*status=}"; req_status="${req_status%% *}"; req_status="${req_status%%|*}"
  [[ "$req_status" == passed ]] || { [[ "$status" != done ]] || fail "done state has required verification $req_status"; }
done < "$TASK_DIR/state.md"
while IFS='|' read -r label command run_at result last_edit rest; do
  [[ "$label" == evidence:* ]] || continue
  run_at="${run_at#*run_at=}"; run_at="${run_at%% *}"
  last_edit="${last_edit#*last_edit_at=}"; last_edit="${last_edit%% *}"
  [[ "$run_at" < "$last_edit" ]] && fail "evidence is stale: ${label#evidence: }"
done < "$TASK_DIR/state.md"
printf 'check-state: passed\n'
