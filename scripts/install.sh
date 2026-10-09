#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST="$HOME/.pi/agent/skills"
UPDATE=0
MODE="copy"
usage() { printf 'usage: %s [--dest DIR] [--update | --link | --unlink]\n' "$0"; }
while (($#)); do
  case "$1" in
    --dest) (($# >= 2)) || { usage >&2; exit 2; }; DEST="$2"; shift 2 ;;
    --update) [[ "$MODE" == copy ]] || { usage >&2; exit 2; }; UPDATE=1; shift ;;
    --link) [[ "$MODE" == copy && "$UPDATE" -eq 0 ]] || { usage >&2; exit 2; }; MODE="link"; shift ;;
    --unlink) [[ "$MODE" == copy && "$UPDATE" -eq 0 ]] || { usage >&2; exit 2; }; MODE="unlink"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

bash "$ROOT/scripts/check-repo.sh"
mkdir -p "$DEST"

runtime_skills() { grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt"; }
skill_list="$(runtime_skills)"
[[ -n "$skill_list" ]] || { printf 'install: %s lists no skill\n' "$ROOT/scripts/runtime-skills.txt" >&2; exit 1; }

source_skill_path() { (cd "$ROOT/skills/$1" && pwd -P); }
resolve_link() {
  local link="$1" target abs dir
  target="$(readlink "$link")" || return 1
  case "$target" in
    /*) abs="$target" ;;
    *) abs="$(dirname "$link")/$target" ;;
  esac
  dir="$(cd "$(dirname "$abs")" 2>/dev/null && pwd -P)" || return 1
  printf '%s/%s' "$dir" "$(basename "$abs")"
}

if [[ "$MODE" == link ]]; then
  while IFS= read -r skill; do
    dst="$DEST/$skill"
    [[ -e "$dst" || -L "$dst" ]] || continue
    if [[ -L "$dst" ]]; then
      resolved="$(resolve_link "$dst")" || { printf 'install: refusing to replace broken link %s\n' "$dst" >&2; exit 1; }
      [[ "$resolved" == "$(source_skill_path "$skill")" ]] || { printf 'install: refusing to replace %s; it points outside this repository\n' "$dst" >&2; exit 1; }
    else
      printf 'install: refusing to replace directory %s; remove it first or use copy mode\n' "$dst" >&2
      exit 1
    fi
  done < <(runtime_skills)
  while IFS= read -r skill; do
    dst="$DEST/$skill"
    if [[ -L "$dst" ]]; then
      rm -- "$dst"
    fi
    ln -s "$ROOT/skills/$skill" "$dst"
  done < <(runtime_skills)
  printf 'install: linked x-work skills into %s\n' "$DEST"
  exit 0
fi

if [[ "$MODE" == unlink ]]; then
  removed=0
  skipped=0
  while IFS= read -r skill; do
    dst="$DEST/$skill"
    if [[ -L "$dst" ]]; then
      resolved="$(resolve_link "$dst" || true)"
      if [[ -n "$resolved" && "$resolved" == "$(source_skill_path "$skill")" ]]; then
        rm -- "$dst"
        removed=$((removed + 1))
      else
        printf 'install: skipped %s (not a link to this repository)\n' "$dst" >&2
        skipped=$((skipped + 1))
      fi
    elif [[ -e "$dst" ]]; then
      printf 'install: skipped %s (not a symlink)\n' "$dst" >&2
      skipped=$((skipped + 1))
    fi
  done < <(runtime_skills)
  printf 'install: unlinked %s skill(s) from %s (%s skipped)\n' "$removed" "$DEST" "$skipped"
  exit 0
fi

# Validate every target before changing any target. This prevents a partial update.
while IFS= read -r skill; do
  dst="$DEST/$skill"
  marker="$dst/.x-work-installed"
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
  printf 'source=%s\ninstalled_at=%s\n' "$ROOT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$dst/.x-work-installed"
done < <(runtime_skills)

printf 'install: installed x-work skills into %s\n' "$DEST"
