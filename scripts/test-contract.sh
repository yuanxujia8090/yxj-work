#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/skills/yxj-work/scripts/check-contract.sh"
fail() { printf 'contract: %s\n' "$1" >&2; exit 1; }
expect_pass() { "$CHECK" "$ROOT/tests/contract-fixtures/$1" >/dev/null || fail "expected pass: $1"; }
expect_fail() { if "$CHECK" "$ROOT/tests/contract-fixtures/$1" >/dev/null 2>&1; then fail "expected failure: $1"; fi; }

expect_pass valid-low
expect_pass valid-medium
expect_pass valid-high
expect_pass legacy
for name in missing-acceptance missing-verification invalid-enum duplicate-acceptance risk-policy-conflict high-risk-exempted medium-confirmation-pending; do
  expect_fail "$name"
done
printf 'contract: passed\n'
