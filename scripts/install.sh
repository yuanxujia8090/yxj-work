#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST="$HOME/.pi/agent/skills"
UPDATE=0
usage() { printf 'usage: %s [--dest DIR] [--update]\n' "$0"; }
while (($#)); do
  case "$1" in
    --dest) (($# >= 2)) || { usage >&2; exit 2; }; DEST="$2"; shift 2 ;;
    --update) UPDATE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

bash "$ROOT/scripts/check-repo.sh"
mkdir -p "$DEST"

runtime_skills() { grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt"; }
skill_list="$(runtime_skills)"
[[ -n "$skill_list" ]] || { printf 'install: %s lists no skill\n' "$ROOT/scripts/runtime-skills.txt" >&2; exit 1; }

# Validate every target before changing any target. This prevents a partial update.
while IFS= read -r skill; do
  dst="$DEST/$skill"
  marker="$dst/.yxj-work-installed"
  if [[ -e "$dst" && "$UPDATE" -ne 1 ]]; then
    printf 'install: refusing to overwrite existing %s (use --update only for a marked install)\n' "$dst" >&2
    exit 1
  fi
  if [[ -e "$dst" && ! -f "$marker" ]]; then
    printf 'install: refusing to overwrite unmarked %s\n' "$dst" >&2
    exit 1
  fi
  if [[ -e "$dst" ]] && ! grep -Fqx "source=$ROOT" "$marker"; then
    printf 'install: refusing to update %s because it belongs to another source repository\n' "$dst" >&2
    exit 1
  fi
done < <(runtime_skills)

while IFS= read -r skill; do
  src="$ROOT/skills/$skill"
  dst="$DEST/$skill"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -R "$src"/. "$dst"/
  printf 'source=%s\ninstalled_at=%s\n' "$ROOT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$dst/.yxj-work-installed"
done < <(runtime_skills)

printf 'install: installed yxj-work skills into %s\n' "$DEST"
