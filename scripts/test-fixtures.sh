#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/skills/yxj-work/scripts/check-state.sh"
fail() { printf 'fixtures: %s\n' "$1" >&2; exit 1; }
expect_pass() { "$CHECK" "$1" >/dev/null || fail "expected pass: $1"; }
expect_fail() { if "$CHECK" "$1" >/dev/null 2>&1; then fail "expected failure: $1"; fi; }

for name in valid-done valid-blocked; do expect_pass "$ROOT/tests/fixtures/$name"; done
for name in done-not-run done-stale threshold-not-blocked blocked-missing-fields; do expect_fail "$ROOT/tests/fixtures/$name"; done
printf 'fixtures: passed\n'
