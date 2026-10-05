#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/skills/yxj-work/scripts/check-contract.sh"
fail() { printf 'contract: %s\n' "$1" >&2; exit 1; }
expect_pass() { "$CHECK" "$ROOT/tests/contract-fixtures/$1" >/dev/null || fail "expected pass: $1"; }
expect_fail() { if "$CHECK" "$ROOT/tests/contract-fixtures/$1" >/dev/null 2>&1; then fail "expected failure: $1"; fi; }
expect_fail_message() {
  local fixture="$1" expected="$2" output
  if output="$($CHECK "$ROOT/tests/contract-fixtures/$fixture" 2>&1)"; then
    fail "expected failure: $fixture"
  fi
  printf '%s\n' "$output" | grep -Fq -- "$expected" || fail "unexpected failure for $fixture: $output"
}

expect_pass valid-low
expect_pass valid-medium
expect_pass valid-high
expect_pass legacy
for name in missing-acceptance missing-verification invalid-enum duplicate-acceptance risk-policy-conflict high-risk-exempted; do
  expect_fail "$name"
done
expect_fail_message medium-confirmation-pending 'confirmation is pending; only --draft is allowed'
"$CHECK" "$ROOT/tests/contract-fixtures/medium-confirmation-pending" --draft >/dev/null || fail 'pending contract should pass in draft mode'

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -R "$ROOT/tests/contract-fixtures/valid-low" "$tmp/task"
mkdir "$tmp/task/audit"
"$CHECK" "$tmp/task" --seal >/dev/null || fail 'valid contract should seal'
[[ -f "$tmp/task/audit/contract-r1.md" ]] || fail 'seal did not create contract snapshot'
"$CHECK" "$tmp/task" --locked >/dev/null || fail 'locked mode rejected unchanged sealed contract'
printf '\n# mutation\n' >> "$tmp/task/contract.md"
if "$CHECK" "$tmp/task" --locked >/dev/null 2>&1; then
  fail 'locked mode accepted contract mutation without revision'
fi
printf 'contract: passed\n'
