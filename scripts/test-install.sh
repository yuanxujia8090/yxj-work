#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-install: %s\n' "$1" >&2; exit 1; }
tmp=''
while (($#)); do
  case "$1" in
    --keep-artifacts) shift ;;
    --test-root) tmp="$2"; shift 2 ;;
    *) fail "invalid option: $1" ;;
  esac
done
if [[ -n "$tmp" ]]; then
  [[ ! -e "$tmp" && ! -L "$tmp" ]] || fail 'test root must be new'
  mkdir -p "$tmp"
else
  tmp="$(mktemp -d)"
fi
bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/fresh" >/dev/null
if bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null 2>&1; then fail 'overwrite accepted'; fi
mkdir "$tmp/foreign"
cp -R "$tmp/fresh"/. "$tmp/foreign"/
printf 'source=/other\ninstalled_at=old\n' > "$tmp/foreign/x-rail-long/.x-rail-installed"
before="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/foreign" --update >/dev/null 2>&1; then fail 'foreign update accepted'; fi
after="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
[[ "$before" == "$after" ]] || fail 'foreign rejection changed files'
mkdir -p "$tmp/unmarked/x-rail"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/unmarked" --update >/dev/null 2>&1; then fail 'unmarked update accepted'; fi
for scenario in linked relative wrong broken markerless; do
  mkdir "$tmp/$scenario"
  while IFS= read -r skill; do
    if [[ "$skill" == x-rail ]]; then
      case "$scenario" in
        relative) target="$(python3 -c 'import os,sys; print(os.path.relpath(os.path.realpath(sys.argv[1]),os.path.realpath(sys.argv[2])))' "$ROOT/skills/$skill" "$tmp/$scenario")" ;;
        wrong) target="$ROOT/skills/x-rail-long" ;;
        broken) target="$tmp/missing" ;;
        markerless) mkdir "$tmp/$scenario/$skill"; cp "$ROOT/skills/$skill/SKILL.md" "$tmp/$scenario/$skill/SKILL.md"; continue ;;
        *) target="$ROOT/skills/$skill" ;;
      esac
    else target="$ROOT/skills/$skill"; fi
    ln -s "$target" "$tmp/$scenario/$skill"
  done < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt")
  case "$scenario" in
    linked|relative) bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/$scenario" >/dev/null ;;
    *) if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/$scenario" >/dev/null 2>&1; then fail "$scenario accepted"; fi ;;
  esac
done
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linkdest" >/dev/null
for scenario in wrong broken directory; do
  mkdir "$tmp/refuse-$scenario"
  case "$scenario" in
    wrong) ln -s "$ROOT/skills/x-rail-long" "$tmp/refuse-$scenario/x-rail" ;;
    broken) ln -s "$tmp/missing" "$tmp/refuse-$scenario/x-rail" ;;
    directory) mkdir "$tmp/refuse-$scenario/x-rail" ;;
  esac
  if bash "$ROOT/scripts/install.sh" --dest "$tmp/refuse-$scenario" --link >/dev/null 2>&1; then fail "link $scenario accepted"; fi
done
for scenario in wrong broken; do
  before_link="$(readlink "$tmp/refuse-$scenario/x-rail")"
  if bash "$ROOT/scripts/install.sh" --dest "$tmp/refuse-$scenario" >/dev/null 2>&1; then fail "copy $scenario accepted"; fi
  [[ -L "$tmp/refuse-$scenario/x-rail" && "$(readlink "$tmp/refuse-$scenario/x-rail")" == "$before_link" ]] || fail 'copy refusal changed link'
done
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link --update >/dev/null 2>&1; then fail 'link+update accepted'; fi
printf 'test-install: passed (copy, links, overwrite refusal, foreign protection); deletion paths blocked; artifacts=%s\n' "$tmp"
