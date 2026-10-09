#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/scripts/check-skill-metadata.sh"
TEST_ROOT="${YXJ_TEST_ROOT:-${TMPDIR:-/tmp}}"
tmp="$(mktemp -d "$TEST_ROOT/metadata.XXXXXX")"
# Keep fixtures available for inspection; they contain only synthetic skill headers.
mkdir -p "$tmp/skills/example"
file="$tmp/skills/example/SKILL.md"
valid=$'---\nname: example\ndescription: 使用场景说明\ndisable-model-invocation: true\n---\n# example'
printf '%s\n' "$valid" > "$file"
bash "$CHECK" "$tmp" >/dev/null
count=1
reject() {
  local expected="$1" text="$2" output
  printf '%s\n' "$text" > "$file"
  if output="$(bash "$CHECK" "$tmp" 2>&1)"; then
    printf 'test-skill-metadata: accepted invalid header: %s\n' "$expected" >&2; exit 1
  fi
  [[ "$output" == *"$expected"* ]] || { printf 'test-skill-metadata: unexpected error: %s\n' "$output" >&2; exit 1; }
  count=$((count + 1))
}
reject 'name mismatch' "${valid/name: example/name: other}"
reject 'missing one-line description' "${valid/description: 使用场景说明/description:   }"
reject 'missing one-line description' "${valid/description: 使用场景说明/description: \"\"}"
reject 'missing invocation boundary' $'---\nname: example\ndescription: 场景\n---\ndisable-model-invocation: true'
reject 'invalid invocation boundary' "${valid/disable-model-invocation: true/disable-model-invocation: false}"
reject 'missing closing frontmatter delimiter' $'---\nname: example\ndescription: 场景\ndisable-model-invocation: true'
reject 'duplicate name' "${valid/name: example/$'name: example\nname: example'}"
reject 'missing opening frontmatter delimiter' $'# example\nname: example'
reject 'missing description' $'---\nname: example\ndisable-model-invocation: true\n---'
printf 'test-skill-metadata: passed (%s cases); fixtures=%s\n' "$count" "$tmp"
