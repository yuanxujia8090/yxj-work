#!/usr/bin/env bash
set -euo pipefail

TASK_DIR="${1:-}"
[[ -n "$TASK_DIR" && -f "$TASK_DIR/state.md" ]] || { printf 'check-state: usage: %s TASK_DIR\n' "$0" >&2; exit 2; }
fail() { printf 'check-state: %s\n' "$1" >&2; exit 1; }
value() { sed -n "s/^$1: //p" "$TASK_DIR/state.md" | head -n 1; }
status="$(value status)"
stage="$(value stage)"
level="$(value level)"
calls="$(value calls_since_progress)"
budget="$(value budget)"
[[ -n "$status" ]] || fail 'missing status'
[[ -n "$stage" ]] || fail 'missing stage'
# Enum must match the route stage names in skills/yxj-work/SKILL.md (check-repo.sh asserts both).
case "$status" in
  in_progress|done|blocked|stopped|cancelled) ;;
  *) fail "invalid status: $status" ;;
esac
# stage: 路由 10 个阶段 + handoff（交接收尾）。done/closed 是 status 误写进 stage，不放行。
case "$stage" in
  fast-answer|investigate|research|design|plan|exec|bugfix|review|ops|mixed|handoff) ;;
  *) fail "invalid stage: $stage" ;;
esac
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
req_count=0
while IFS= read -r line; do
  [[ "$line" == required_verification:* ]] || continue
  req_count=$((req_count + 1))
  req_status="${line##*status=}"; req_status="${req_status%% *}"; req_status="${req_status%%|*}"
  [[ "$req_status" == passed ]] || { [[ "$status" != done ]] || fail "done state has required verification $req_status"; }
done < "$TASK_DIR/state.md"
if [[ "$status" == done && "$req_count" -eq 0 ]]; then
  fail 'done state has no required_verification'
fi
# Reject invalid/zero-padding-deficient timestamps; normalize to a fixed-width prefix
# (YYYY-MM-DDTHH:MM) so string comparison keeps correct order.
evidence_ts() {
  local v="$1" field="$2" ev="$3"
  [[ -n "$v" ]] || fail "evidence $ev: missing $field"
  v="${v// /T}"
  if [[ "$v" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2})((T[0-9]{2}:[0-9]{2})(:[0-9]{2})?([Zz]|[+-][0-9]{2}(:[0-9]{2})?)?)?$ ]]; then
    if [[ -n "${BASH_REMATCH[3]}" ]]; then
      printf '%s%s' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    else
      printf '%sT00:00' "${BASH_REMATCH[1]}"
    fi
  else
    fail "evidence $ev: invalid $field: $1 (expected YYYY-MM-DD[THH:MM[:SS][Z|+hh:mm]])"
  fi
}
while IFS= read -r line; do
  [[ "$line" == evidence:* ]] || continue
  ev="${line%%|*}"
  ev="${ev#evidence:}"
  run_at=''
  last_edit=''
  if [[ "$line" =~ \|run_at=([^|]*) ]]; then run_at="${BASH_REMATCH[1]}"; fi
  if [[ "$line" =~ \|last_edit_at=([^|]*) ]]; then last_edit="${BASH_REMATCH[1]}"; fi
  run_norm="$(evidence_ts "$run_at" run_at "$ev")"
  edit_norm="$(evidence_ts "$last_edit" last_edit_at "$ev")"
  [[ "$run_norm" < "$edit_norm" ]] && fail "evidence is stale: $ev"
done < "$TASK_DIR/state.md"
printf 'check-state: passed\n'
