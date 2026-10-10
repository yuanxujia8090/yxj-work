#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CHECK="$ROOT/scripts/check-skill-metadata.sh"
tmp=''
while (($#)); do
  case "$1" in
    --keep-artifacts) shift ;;
    --test-root) tmp="$2"; shift 2 ;;
    *) printf 'test-skill-metadata: invalid option\n' >&2; exit 2 ;;
  esac
done
if [[ -n "$tmp" ]]; then
  [[ ! -e "$tmp" && ! -L "$tmp" ]] || { printf 'test-skill-metadata: test root must be new\n' >&2; exit 1; }
  mkdir -p "$tmp"
else
  tmp="$(mktemp -d)"
fi
mkdir -p "$tmp/skills/example"
file="$tmp/skills/example/SKILL.md"
valid=$'---\nname: example\ndescription: 使用场景说明\ndisable-model-invocation: true\n---\n# example'
count=0
accept() {
  local text="$1"
  printf '%s\n' "$text" > "$file"
  bash "$CHECK" "$tmp" >/dev/null || { printf 'test-skill-metadata: rejected valid header\n' >&2; exit 1; }
  count=$((count + 1))
}
reject() {
  local expected="$1" text="$2" output
  printf '%s\n' "$text" > "$file"
  if output="$(bash "$CHECK" "$tmp" 2>&1)"; then
    printf 'test-skill-metadata: accepted invalid header: %s\n' "$expected" >&2; exit 1
  fi
  [[ "$output" == *"$expected"* ]] || { printf 'test-skill-metadata: unexpected error: %s\n' "$output" >&2; exit 1; }
  count=$((count + 1))
}
bad_string='description must be a non-empty one-line string'
accept "$valid"
accept "${valid/description: 使用场景说明/description: \"使用场景说明\"}"
accept "${valid/description: 使用场景说明/description: '场景'}"
accept "${valid/description: 使用场景说明/description: 使用场景说明 # 注释}"
accept "${valid/name: example/name: \"example\"}"
reject 'name mismatch' "${valid/name: example/name: other}"
reject "$bad_string" "${valid/description: 使用场景说明/description:   }"
reject "$bad_string" "${valid/description: 使用场景说明/description: \"\"}"
reject "$bad_string" "${valid/description: 使用场景说明/description: \"\" # empty}"
reject "$bad_string" "${valid/description: 使用场景说明/description: ''}"
reject "$bad_string" "${valid/description: 使用场景说明/description: []}"
reject "$bad_string" "${valid/description: 使用场景说明/description: false}"
reject "$bad_string" "${valid/description: 使用场景说明/description: >-}"
reject "$bad_string" "${valid/description: 使用场景说明/description: |+}"
reject "$bad_string" "${valid/description: 使用场景说明/description: 123}"
reject "$bad_string" "${valid/description: 使用场景说明/description: \"未闭合}"
reject 'non-canonical key spacing' "${valid/name: example/name : example}"
reject 'non-canonical key spacing' "${valid/description: 使用场景说明/description : 场景}"
reject 'missing invocation boundary' $'---\nname: example\ndescription: 场景\n---\ndisable-model-invocation: true'
reject 'invalid invocation boundary' "${valid/disable-model-invocation: true/disable-model-invocation: false}"
reject 'missing closing frontmatter delimiter' $'---\nname: example\ndescription: 场景\ndisable-model-invocation: true'
reject 'duplicate name' "${valid/name: example/$'name: example\nname: example'}"
reject 'missing opening frontmatter delimiter' $'# example\nname: example'
reject 'missing description' $'---\nname: example\ndisable-model-invocation: true\n---'
printf 'test-skill-metadata: passed (%s cases); fixtures=%s\n' "$count" "$tmp"
