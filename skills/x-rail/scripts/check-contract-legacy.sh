#!/usr/bin/env bash
set -euo pipefail

TASK_DIR="${1:-}"
MODE="${2:---ready}"
case "$MODE" in --draft|--ready|--seal|--locked) ;; *) printf 'check-contract: invalid mode\n' >&2; exit 2 ;; esac
[[ -n "$TASK_DIR" && -f "$TASK_DIR/contract.md" ]] || {
  printf 'check-contract: usage: %s TASK_DIR\n' "${0##*/}" >&2
  exit 2
}
CONTRACT="$TASK_DIR/contract.md"
fail() { printf 'check-contract: %s\n' "$1" >&2; exit 1; }
field() {
  local key="$1"
  sed -n "s/^${key}: //p" "$CONTRACT" | head -n 1
}
require_field() {
  local key="$1" value
  value="$(field "$key")"
  [[ -n "$value" ]] || fail "missing field: $key"
}
one_of() {
  local key="$1" value allowed
  value="$(field "$key")"
  shift
  for allowed in "$@"; do [[ "$value" == "$allowed" ]] && return 0; done
  fail "invalid $key: ${value:-<empty>}"
}
section_field() {
  local id="$1" key="$2"
  awk -v id="$id" -v key="$key" '
    /^## / { acceptance=($0 == "## Acceptance"); in_section=0 }
    /^### / { in_section=acceptance && ($0 == "### " id); next }
    in_section && index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }
  ' "$CONTRACT"
}
# Contract fields are line-oriented and must start at column 1. Catch the common
# Markdown-list mistake early so the error points to the format instead of a
# misleading "missing field" message.
if grep -Eq '^- [a-z_]+:' "$CONTRACT"; then
  fail 'fields must use key: value at column 1; remove list markers'
fi

# Reject duplicates and fields outside their declared sections; otherwise a later
# conflicting value could be invisible to the first-value parser above.
awk '
  function die(msg) { print "check-contract: " msg > "/dev/stderr"; exit 1 }
  /^## / {
    section=substr($0, 4); id=""
    if (++sections[section] > 1) die("duplicate section: " section)
    next
  }
  /^### / {
    if (section == "Acceptance") {
      if ($0 !~ /^### A[1-9][0-9]*$/) die("invalid acceptance heading: " $0)
      id=substr($0, 5)
      if (++ids[id] > 1) die("duplicate acceptance id: " id)
    }
    next
  }
  /^[a-z_]+:/ {
    key=$0; sub(/:.*/, "", key)
    if (section == "Acceptance" && id == "") die("acceptance field without id")
    if (++fields[section SUBSEP id SUBSEP key] > 1) die("duplicate field: " key)
  }
' "$CONTRACT" || exit 1

# Historical contracts remain readable and are not forced into the v2 format.
# A partially migrated contract is not legacy: once v2 fields appear, Acceptance is required.
if ! grep -Fqx '## Acceptance' "$CONTRACT"; then
  if [[ -z "$(field objective)" && -z "$(field risk)" && -z "$(field contract_revision)" ]]; then
    printf 'check-contract: legacy contract (v2 checks skipped)\n'
    printf 'check-contract: passed\n'
    exit 0
  fi
  fail 'missing section: Acceptance'
fi

for key in task_id level task_type objective scope forbidden risk risk_reason review_policy contract_revision done_when; do
  require_field "$key"
done
one_of level L1 L2 L3 long
one_of task_type investigate research design plan exec bugfix review ops mixed
for section in Unknowns 'Decision Gates' 'Contract Changes'; do
  grep -Fqx "## $section" "$CONTRACT" || fail "missing section: $section"
done
one_of risk low medium high
one_of review_policy auto user-confirm full-review
revision="$(field contract_revision)"
[[ "$revision" =~ ^[1-9][0-9]*$ ]] || fail "invalid contract_revision: $revision"

acceptance_count="$(awk '/^## / { a=($0 == "## Acceptance") } a && /^### A[1-9][0-9]*$/ { count++ } END { print count + 0 }' "$CONTRACT")"
(( acceptance_count > 0 )) || fail 'Acceptance has no conditions'
ids="$(awk '/^## / { a=($0 == "## Acceptance") } a && /^### A[1-9][0-9]*$/ { sub(/^### /, ""); print }' "$CONTRACT")"
required_count=0
duplicate="$(printf '%s\n' "$ids" | sort | uniq -d | head -n 1)"
[[ -z "$duplicate" ]] || fail "duplicate acceptance id: $duplicate"

while IFS= read -r id; do
  [[ -n "$id" ]] || continue
  for key in outcome verification verification_type layer required; do
    value="$(section_field "$id" "$key")"
    [[ -n "$value" ]] || fail "$id missing field: $key"
  done
  verification_type="$(section_field "$id" verification_type)"
  layer="$(section_field "$id" layer)"
  required="$(section_field "$id" required)"
  case "$verification_type" in automatic|manual|consumer|external) ;; *) fail "$id invalid verification_type: $verification_type" ;; esac
  case "$layer" in syntax/config|static|runtime/local|external|consumer) ;; *) fail "$id invalid layer: $layer" ;; esac
  case "$required" in
    yes) required_count=$((required_count + 1)) ;;
    no) [[ -n "$(section_field "$id" skip_reason)" ]] || fail "$id optional condition needs skip_reason" ;;
    *) fail "$id invalid required: $required" ;;
  esac
done <<EOF
$ids
EOF

(( required_count > 0 )) || fail 'Acceptance needs at least one required condition'
gate_field() {
  awk -v key="$1" '/^## / { gate=($0 == "## Decision Gates") } gate && index($0, key ": ") == 1 { print substr($0, length(key)+3); exit }' "$CONTRACT"
}
for key in confirmation confirmation_status review; do
  value="$(gate_field "$key")"
  [[ -n "$value" ]] || fail "Decision Gates missing field: $key"
done
confirmation="$(gate_field confirmation)"
confirmation_status="$(gate_field confirmation_status)"
review="$(gate_field review)"
case "$confirmation" in required|exempted) ;; *) fail "invalid confirmation: $confirmation" ;; esac
case "$confirmation_status" in pending|confirmed|exempted) ;; *) fail "invalid confirmation_status: $confirmation_status" ;; esac
case "$review" in auto|user-confirm|full-review) ;; *) fail "invalid review: $review" ;; esac

risk="$(field risk)"
review_policy="$(field review_policy)"
case "$risk:$review_policy" in
  medium:auto) fail 'medium risk cannot use auto review_policy' ;;
  high:full-review) ;;
  high:*) fail 'high risk requires full-review policy' ;;
esac
if [[ "$risk" == high && "$confirmation" == exempted ]]; then
  fail 'high risk cannot exempt confirmation'
fi
if [[ "$risk" != low && "$confirmation" != required ]]; then
  fail "$risk risk requires confirmation: required"
fi

[[ "$review" == "$review_policy" ]] || fail 'review conflicts with review_policy'
if [[ "$confirmation" == exempted ]]; then
  [[ "$confirmation_status" == exempted ]] || fail 'exempted confirmation needs exempted status'
  [[ -n "$(gate_field confirmation_reason)" ]] || fail 'exempted confirmation needs reason'
else
  [[ "$confirmation_status" != exempted ]] || fail 'required confirmation cannot have exempted status'
  if [[ "$confirmation_status" == confirmed ]]; then
    for key in confirmation_by confirmation_at confirmation_source; do
      v="$(gate_field "$key")"
      [[ -n "$v" && "$v" != none ]] || fail "confirmed gate needs $key"
    done
  elif [[ "$MODE" != --draft ]]; then
    fail 'confirmation is pending; only --draft is allowed'
  fi
fi

# Sealing is explicit: the read-only default checker never modifies a contract.
# Each revision is a content snapshot; later revisions require a change record.
audit="$TASK_DIR/audit"
snapshot="$audit/contract-r${revision}.md"
validate_history() {
  local n record key v
  for (( n=1; n<=revision; n++ )); do
    if [[ "$n" -lt "$revision" || "$MODE" == --locked ]]; then
      [[ -f "$audit/contract-r${n}.md" ]] || fail "missing contract snapshot r$n"
    fi
    (( n > 1 )) || continue
    record="$audit/contract-change-r${n}.md"
    [[ -f "$record" ]] || fail "missing change record r$n"
    for key in old_revision new_revision old_value new_value reason approved_by approval_source affected_evidence; do
      v="$(sed -n "s/^${key}: //p" "$record")"
      [[ -n "$v" ]] || fail "change r$n missing $key"
    done
    [[ "$(sed -n 's/^old_revision: //p' "$record")" == "$((n-1))" ]] || fail "change r$n old revision mismatch"
    [[ "$(sed -n 's/^new_revision: //p' "$record")" == "$n" ]] || fail "change r$n new revision mismatch"
    grep -Fq "audit/contract-change-r${n}.md" "$CONTRACT" || fail "Contract Changes missing record r$n"
  done
}
if [[ "$MODE" == --seal || "$MODE" == --locked ]]; then
  validate_history
  if [[ -f "$snapshot" ]]; then
    cmp -s "$CONTRACT" "$snapshot" || fail 'contract changed without a new revision'
  elif [[ "$MODE" == --seal ]]; then
    mkdir -p "$audit"
    (set -o noclobber; cat "$CONTRACT" > "$snapshot") || fail 'snapshot already exists; inspect before continuing'
  fi
fi
printf 'check-contract: passed\n'
