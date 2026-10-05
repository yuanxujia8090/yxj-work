#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/skills/yxj-work/scripts/check-state.sh"
fail() { printf 'fixtures: %s\n' "$1" >&2; exit 1; }
expect_pass() { "$CHECK" "$1" >/dev/null || fail "expected pass: $1"; }
expect_fail() { if "$CHECK" "$1" >/dev/null 2>&1; then fail "expected failure: $1"; fi; }

for name in valid-done valid-blocked valid-space-timestamp valid-field-order contract-linked-valid; do expect_pass "$ROOT/tests/fixtures/$name"; done
for name in done-not-run done-stale threshold-not-blocked blocked-missing-fields invalid-status invalid-stage invalid-timestamp stale-space-timestamp invalid-hour-timestamp budget-exhausted-done done-no-required contract-revision-mismatch acceptance-reference-missing required-acceptance-missing contract-fingerprint-mismatch; do expect_fail "$ROOT/tests/fixtures/$name"; done
printf 'fixtures: passed\n'
