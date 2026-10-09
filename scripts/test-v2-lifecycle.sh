#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CONTRACT_CHECK="$ROOT/skills/x-work/scripts/check-contract.sh"
STATE_CHECK="$ROOT/skills/x-work/scripts/check-state.sh"
fail() { printf 'v2-lifecycle: %s\n' "$1" >&2; exit 1; }
expect_fail() {
  local expected="$1"; shift
  local output
  if output="$("$@" 2>&1)"; then fail "expected failure: $expected"; fi
  printf '%s\n' "$output" | grep -Fq -- "$expected" || fail "unexpected failure: $output"
}

expect_fail 'confirmation is pending; only --draft is allowed' \
  "$CONTRACT_CHECK" "$ROOT/tests/contract-fixtures/medium-confirmation-pending"
"$CONTRACT_CHECK" "$ROOT/tests/contract-fixtures/medium-confirmation-pending" --draft >/dev/null
"$STATE_CHECK" "$ROOT/tests/fixtures/v2-review-valid" >/dev/null

expect_fail 'evidence check missing result' \
  "$STATE_CHECK" "$ROOT/tests/fixtures/v2-evidence-incomplete"
expect_fail 'review evidence required for user-confirm' \
  "$STATE_CHECK" "$ROOT/tests/fixtures/v2-review-missing"

printf 'v2-lifecycle: passed\n'
