#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-install: %s\n' "$1" >&2; exit 1; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/fresh" >/dev/null
[[ -x "$ROOT/scripts/test-flow.sh" ]] || fail 'flow test is not executable'
[[ -x "$ROOT/skills/x-rail/scripts/check-contract.sh" ]] || fail 'contract checker is not executable'
[[ -x "$ROOT/scripts/check-skill-metadata.sh" ]] || fail 'skill metadata checker is not executable'
if bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null 2>&1; then fail 'no-update overwrite was accepted'; fi
bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" --update >/dev/null

mkdir "$tmp/foreign"
cp -R "$tmp/fresh"/. "$tmp/foreign"/
printf 'source=/other\ninstalled_at=old\n' > "$tmp/foreign/x-rail-long/.x-rail-installed"
before="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/foreign" --update >/dev/null 2>&1; then fail 'foreign source update was accepted'; fi
after="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
[[ "$before" == "$after" ]] || fail 'foreign source refusal partially changed targets'

mkdir -p "$tmp/unmarked/x-rail"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/unmarked" --update >/dev/null 2>&1; then fail 'unmarked update was accepted'; fi

# Symlink deployments (the real setup in ~/.pi/agent/skills) must pass without markers.
mkdir "$tmp/linked"
while IFS= read -r skill; do
  ln -s "$ROOT/skills/$skill" "$tmp/linked/$skill"
done < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt")
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null

# Relative-path links: compute from physical paths (/var -> /private/var on macOS),
# matching how the kernel resolves ".." through a symlinked prefix.
rel="$(python3 -c 'import os, sys; print(os.path.relpath(os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])))' "$ROOT/skills/x-rail" "$tmp/linked")"
rm "$tmp/linked/x-rail"
ln -s "$rel" "$tmp/linked/x-rail"
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null
rm "$tmp/linked/x-rail"
ln -s "$ROOT/skills/x-rail" "$tmp/linked/x-rail"

# A link pointing at the wrong skill must be rejected.
rm "$tmp/linked/x-rail"
ln -s "$ROOT/skills/x-rail-long" "$tmp/linked/x-rail"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'wrong-target link was accepted'; fi

# A broken link must be rejected.
rm "$tmp/linked/x-rail"
ln -s "$tmp/does-not-exist" "$tmp/linked/x-rail"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'broken link was accepted'; fi

# A copied skill mixed into a linked install still needs its marker.
rm "$tmp/linked/x-rail"
mkdir "$tmp/linked/x-rail"
cp "$ROOT/skills/x-rail/SKILL.md" "$tmp/linked/x-rail/SKILL.md"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'markerless copy in linked install was accepted'; fi

# install.sh --link builds symlinks; --unlink removes only links into this repository.
mkdir "$tmp/linkdest"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linkdest" >/dev/null
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null

rm "$tmp/linkdest/x-rail"
ln -s "$ROOT/skills/x-rail-long" "$tmp/linkdest/x-rail"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode accepted a wrong-target link'; fi

rm "$tmp/linkdest/x-rail"
ln -s "$tmp/does-not-exist" "$tmp/linkdest/x-rail"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode accepted a broken link'; fi

rm "$tmp/linkdest/x-rail"
mkdir "$tmp/linkdest/x-rail"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode replaced a directory'; fi
rmdir "$tmp/linkdest/x-rail"

if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link --update >/dev/null 2>&1; then fail 'link+update combination was accepted'; fi

ln -s "$ROOT/skills/x-rail" "$tmp/linkdest/x-rail"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null
left="$(find "$tmp/linkdest" -maxdepth 1 -type l | wc -l | tr -d ' ')"
if [[ "$left" != 0 ]]; then fail "unlink left $left symlink(s) behind"; fi

ln -s "$tmp/elsewhere" "$tmp/linkdest/x-rail"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ ! -L "$tmp/linkdest/x-rail" ]]; then fail 'unlink removed a foreign link'; fi
rm "$tmp/linkdest/x-rail"

touch "$tmp/linkdest/x-why"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ ! -f "$tmp/linkdest/x-why" ]]; then fail 'unlink removed a non-symlink entry'; fi

# Unlink on a mixed tree in one pass: repo links removed, foreign links and plain files kept.
ln -s "$ROOT/skills/x-rail" "$tmp/linkdest/x-rail"
ln -s "$tmp/elsewhere" "$tmp/linkdest/x-architect"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ -e "$tmp/linkdest/x-rail" || -L "$tmp/linkdest/x-rail" ]]; then fail 'mixed unlink removed a repo link'; fi
if [[ ! -L "$tmp/linkdest/x-architect" ]]; then fail 'mixed unlink removed a foreign link'; fi
if [[ ! -f "$tmp/linkdest/x-why" ]]; then fail 'mixed unlink removed a plain file'; fi

printf 'test-install: passed\n'
