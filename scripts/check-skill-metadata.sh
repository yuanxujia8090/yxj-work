#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-}"
[[ -n "$ROOT" && -d "$ROOT/skills" ]] || { printf 'check-skill-metadata: usage: %s REPO_ROOT\n' "$0" >&2; exit 2; }
ROOT="$(cd "$ROOT" && pwd -P)"
fail() { printf 'check-skill-metadata: %s\n' "$1" >&2; exit 1; }
count=0
while IFS= read -r file; do
  count=$((count + 1))
  dir_name="$(basename "$(dirname "$file")")"
  # This repository uses one-line scalars for the three required header fields.
  awk -v expected="$dir_name" '
    function error(message) { print "check-skill-metadata: " message " in " FILENAME > "/dev/stderr"; failed=1; exit 1 }
    NR == 1 { if ($0 != "---") error("missing opening frontmatter delimiter"); next }
    $0 == "---" { closed=1; exit }
    /^(name|description|disable-model-invocation):/ {
      key=$0; sub(/:.*/, "", key)
      if (++seen[key] > 1) error("duplicate " key)
      value=$0; sub(/^[^:]*:[[:space:]]*/, "", value); sub(/[[:space:]]*$/, "", value)
      if (key == "name" && value != expected) error("name mismatch; expected " expected)
      if (key == "description" && (value == "" || value == "\"\"" || value == "\047\047" || value == "|" || value == ">" || value == "null" || value == "~" || value ~ /^#/)) error("missing one-line description")
      if (key == "disable-model-invocation" && value != "true") error("invalid invocation boundary")
    }
    END {
      if (failed) exit 1
      if (!closed) error("missing closing frontmatter delimiter")
      if (!seen["name"]) error("missing name")
      if (!seen["description"]) error("missing description")
      if (!seen["disable-model-invocation"]) error("missing invocation boundary")
    }
  ' "$file" || exit 1
done < <(find "$ROOT/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -print | sort)
[[ "$count" -gt 0 ]] || fail 'no skill files found'
printf 'check-skill-metadata: passed (%s skills)\n' "$count"
