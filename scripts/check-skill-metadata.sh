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
  # Only one-line scalars are accepted for the three required header fields. The checker is
  # deliberately fail-closed: a spelling the host loader would reject, or silently turn into a
  # non-string, and a non-canonical key spelling this checker would otherwise skip, are reported.
  awk -v expected="$dir_name" '
    function error(message) { print "check-skill-metadata: " message " in " FILENAME > "/dev/stderr"; failed=1; exit 1 }
    # 1 when the raw scalar cannot load as a non-empty string through the host YAML loader:
    # empty, quoted-but-blank, unterminated quote, flow collection, block scalar, tag/anchor/alias,
    # comment-only, null/bool keyword, or a bare number.
    function bad_string(v,   q, n, i, c, end, inner, rest) {
      if (v == "") return 1
      q = substr(v, 1, 1)
      if (q == "\"" || q == "\047") {
        n = length(v); i = 2
        while (i <= n) {
          c = substr(v, i, 1)
          if (q == "\"" && c == "\\") { i += 2; continue }
          if (c == q) {
            if (q == "\047" && substr(v, i + 1, 1) == "\047") { i += 2; continue }
            end = i; break
          }
          i++
        }
        if (!end) return 1
        rest = substr(v, end + 1)
        if (rest !~ /^[[:space:]]*(#.*)?$/) return 1
        inner = substr(v, 2, end - 2); gsub(/[[:space:]]/, "", inner)
        return (inner == "")
      }
      if (v ~ /^[|>]/ || v ~ /^[[{]/ || v ~ /^[&*!%@]/ || v ~ /^#/) return 1
      if (tolower(v) == "null" || v == "~") return 1
      if (tolower(v) ~ /^(true|false|yes|no|on|off)$/) return 1
      if (v ~ /^[-+]?[0-9]+([.][0-9]+)?$/) return 1
      return 0
    }
    NR == 1 { if ($0 != "---") error("missing opening frontmatter delimiter"); next }
    $0 == "---" { closed=1; exit }
    # YAML also allows "key : value", but this repository only accepts the canonical spelling, and
    # silently skipping the other spelling hides a duplicate or a wrong name.
    /^[A-Za-z][A-Za-z0-9_-]*[ \t]+:/ { error("non-canonical key spacing; write key: value") }
    /^(name|description|disable-model-invocation):/ {
      key=$0; sub(/:.*/, "", key)
      if (++seen[key] > 1) error("duplicate " key)
      value=$0; sub(/^[^:]*:[[:space:]]*/, "", value); sub(/[[:space:]]*$/, "", value)
      if (key == "name") {
        name=value; q=substr(name, 1, 1)
        if ((q == "\"" || q == "\047") && length(name) >= 2 && substr(name, length(name), 1) == q) name=substr(name, 2, length(name) - 2)
        if (name != expected) error("name mismatch; expected " expected)
      }
      if (key == "description" && bad_string(value)) error("description must be a non-empty one-line string")
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
