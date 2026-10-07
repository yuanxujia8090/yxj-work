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
# New contracts bind verification names and state to an explicit contract revision.
# Legacy tasks without Acceptance keep the v1 checks below.
if [[ -f "$TASK_DIR/contract.md" ]] && grep -Fqx '## Acceptance' "$TASK_DIR/contract.md"; then
  contract_revision="$(sed -n 's/^contract_revision: //p' "$TASK_DIR/contract.md" | head -n 1)"
  evidence_schema="$(value evidence_schema)"
  if [[ -n "$evidence_schema" && "$evidence_schema" != 2 ]]; then
    fail "invalid evidence_schema: $evidence_schema"
  fi
  state_revision="$(value contract_revision)"
  [[ -n "$state_revision" && "$state_revision" == "$contract_revision" ]] || fail 'contract_revision mismatch or missing in state'
  contract_fingerprint="$(shasum -a 256 "$TASK_DIR/contract.md" | awk '{print $1}')"
  state_fingerprint="$(value contract_fingerprint)"
  [[ -n "$state_fingerprint" && "$state_fingerprint" == "$contract_fingerprint" ]] || fail 'contract_fingerprint mismatch or missing in state'
  required_acceptance_ids="$(awk '/^## / { a=($0 == "## Acceptance") } a && /^### A[1-9][0-9]*$/ { id=$0; sub(/^### /, "", id); next } a && id == "" { next } a && /^required: yes$/ { print id; id="" }' "$TASK_DIR/contract.md")"
  while IFS= read -r line; do
    [[ "$line" == required_verification:* ]] || continue
    acceptance_id="${line#required_verification: }"; acceptance_id="${acceptance_id%% *}"
    grep -Fqx "### $acceptance_id" "$TASK_DIR/contract.md" || fail "unknown acceptance reference: $acceptance_id"
  done < "$TASK_DIR/state.md"
  if [[ "$status" == done ]]; then
    while IFS= read -r acceptance_id; do
      [[ -n "$acceptance_id" ]] || continue
      grep -Eq "^required_verification: ${acceptance_id} status=passed( |$)" "$TASK_DIR/state.md" || fail "required acceptance not passed: $acceptance_id"
    done <<EOF
$required_acceptance_ids
EOF
  fi
fi
req_count=0
while IFS= read -r line; do
  [[ "$line" == required_verification:* ]] || continue
  req_count=$((req_count + 1))
  req_status="${line##*status=}"; req_status="${req_status%% *}"; req_status="${req_status%%|*}"
  [[ "$req_status" == passed ]] || { [[ "$status" != done ]] || fail "done state has required verification $req_status"; }
  if [[ "${evidence_schema:-}" == 2 ]]; then
    evidence_ref="${line##*evidence=}"; evidence_ref="${evidence_ref%% *}"; evidence_ref="${evidence_ref%%|*}"
    [[ -n "$evidence_ref" ]] || fail "required verification missing evidence: ${line#required_verification: }"
    [[ -f "$TASK_DIR/$evidence_ref" ]] || fail "evidence file not found: $evidence_ref"
    evidence_id="${evidence_ref##*/}"; evidence_id="${evidence_id%.txt}"
    evidence_line="$(grep -E "^evidence:${evidence_id}(\\||$)" "$TASK_DIR/state.md" | head -n 1 || true)"
    [[ -n "$evidence_line" ]] || fail "evidence not found: $evidence_id"
    acceptance_id="${line#required_verification: }"; acceptance_id="${acceptance_id%% *}"
    evidence_acceptance="$(printf '%s\n' "$evidence_line" | sed -n 's/.*|acceptance=\([^|]*\).*/\1/p')"
    [[ "$evidence_acceptance" == "$acceptance_id" ]] || fail "evidence $evidence_id is not bound to $acceptance_id"
    for evidence_key in command run_at result last_edit_at; do
      evidence_value="$(printf '%s\n' "$evidence_line" | sed -n "s/.*|${evidence_key}=\([^|]*\).*/\1/p")"
      [[ -n "$evidence_value" ]] || fail "evidence $evidence_id missing $evidence_key"
    done
    evidence_result="$(printf '%s\n' "$evidence_line" | sed -n 's/.*|result=\([^|]*\).*/\1/p')"
    [[ "$req_status" != passed || "$evidence_result" == passed ]] || fail "evidence $evidence_id is not passed"
  fi
done < "$TASK_DIR/state.md"
if [[ "$status" == done && "$req_count" -eq 0 ]]; then
  fail 'done state has no required_verification'
fi
if [[ "${evidence_schema:-}" == 2 && "$status" == done ]]; then
  review_policy="$(sed -n 's/^review_policy: //p' "$TASK_DIR/contract.md" | head -n 1)"
  if [[ "$review_policy" != auto ]]; then
    review_line="$(grep '^review_evidence:' "$TASK_DIR/state.md" | head -n 1 || true)"
    [[ -n "$review_line" ]] || fail "review evidence required for $review_policy"
    review_policy_record="$(printf '%s\n' "$review_line" | sed -n 's/.*|policy=\([^|]*\).*/\1/p')"
    review_status="$(printf '%s\n' "$review_line" | sed -n 's/.*|status=\([^|]*\).*/\1/p')"
    review_path="$(printf '%s\n' "$review_line" | sed -n 's/.*|path=\([^|]*\).*/\1/p')"
    [[ "$review_policy_record" == "$review_policy" ]] || fail 'review evidence policy mismatch'
    [[ "$review_status" == passed ]] || fail 'review evidence is not passed'
    [[ -n "$review_path" ]] || fail 'review evidence missing path'
    [[ -f "$TASK_DIR/$review_path" ]] || fail "review evidence file not found: $review_path"
  fi
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
