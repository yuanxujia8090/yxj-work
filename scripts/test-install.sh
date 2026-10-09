#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-install: %s\n' "$1" >&2; exit 1; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/fresh" >/dev/null
[[ -x "$ROOT/scripts/test-flow.sh" ]] || fail 'flow test is not executable'
[[ -x "$ROOT/skills/x-work/scripts/check-contract.sh" ]] || fail 'contract checker is not executable'
[[ -x "$ROOT/scripts/check-skill-metadata.sh" ]] || fail 'skill metadata checker is not executable'
if bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null 2>&1; then fail 'no-update overwrite was accepted'; fi
bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" --update >/dev/null

mkdir "$tmp/foreign"
cp -R "$tmp/fresh"/. "$tmp/foreign"/
printf 'source=/other\ninstalled_at=old\n' > "$tmp/foreign/x-work-long/.x-work-installed"
before="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/foreign" --update >/dev/null 2>&1; then fail 'foreign source update was accepted'; fi
after="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
[[ "$before" == "$after" ]] || fail 'foreign source refusal partially changed targets'

mkdir -p "$tmp/unmarked/x-work"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/unmarked" --update >/dev/null 2>&1; then fail 'unmarked update was accepted'; fi

# Symlink deployments (the real setup in ~/.pi/agent/skills) must pass without markers.
mkdir "$tmp/linked"
while IFS= read -r skill; do
  ln -s "$ROOT/skills/$skill" "$tmp/linked/$skill"
done < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/scripts/runtime-skills.txt")
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null

# Relative-path links: compute from physical paths (/var -> /private/var on macOS),
# matching how the kernel resolves ".." through a symlinked prefix.
rel="$(python3 -c 'import os, sys; print(os.path.relpath(os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])))' "$ROOT/skills/x-work" "$tmp/linked")"
rm "$tmp/linked/x-work"
ln -s "$rel" "$tmp/linked/x-work"
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null
rm "$tmp/linked/x-work"
ln -s "$ROOT/skills/x-work" "$tmp/linked/x-work"

# A link pointing at the wrong skill must be rejected.
rm "$tmp/linked/x-work"
ln -s "$ROOT/skills/x-work-long" "$tmp/linked/x-work"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'wrong-target link was accepted'; fi

# A broken link must be rejected.
rm "$tmp/linked/x-work"
ln -s "$tmp/does-not-exist" "$tmp/linked/x-work"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'broken link was accepted'; fi

# A copied skill mixed into a linked install still needs its marker.
rm "$tmp/linked/x-work"
mkdir "$tmp/linked/x-work"
cp "$ROOT/skills/x-work/SKILL.md" "$tmp/linked/x-work/SKILL.md"
if bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linked" >/dev/null 2>&1; then fail 'markerless copy in linked install was accepted'; fi

# install.sh --link builds symlinks; --unlink removes only links into this repository.
mkdir "$tmp/linkdest"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/linkdest" >/dev/null
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null

rm "$tmp/linkdest/x-work"
ln -s "$ROOT/skills/x-work-long" "$tmp/linkdest/x-work"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode accepted a wrong-target link'; fi

rm "$tmp/linkdest/x-work"
ln -s "$tmp/does-not-exist" "$tmp/linkdest/x-work"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode accepted a broken link'; fi

rm "$tmp/linkdest/x-work"
mkdir "$tmp/linkdest/x-work"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link >/dev/null 2>&1; then fail 'link mode replaced a directory'; fi
rmdir "$tmp/linkdest/x-work"

if bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --link --update >/dev/null 2>&1; then fail 'link+update combination was accepted'; fi

ln -s "$ROOT/skills/x-work" "$tmp/linkdest/x-work"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null
left="$(find "$tmp/linkdest" -maxdepth 1 -type l | wc -l | tr -d ' ')"
if [[ "$left" != 0 ]]; then fail "unlink left $left symlink(s) behind"; fi

ln -s "$tmp/elsewhere" "$tmp/linkdest/x-work"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ ! -L "$tmp/linkdest/x-work" ]]; then fail 'unlink removed a foreign link'; fi
rm "$tmp/linkdest/x-work"

touch "$tmp/linkdest/x-why"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ ! -f "$tmp/linkdest/x-why" ]]; then fail 'unlink removed a non-symlink entry'; fi

# Unlink on a mixed tree in one pass: repo links removed, foreign links and plain files kept.
ln -s "$ROOT/skills/x-work" "$tmp/linkdest/x-work"
ln -s "$tmp/elsewhere" "$tmp/linkdest/x-architect"
bash "$ROOT/scripts/install.sh" --dest "$tmp/linkdest" --unlink >/dev/null 2>&1
if [[ -e "$tmp/linkdest/x-work" || -L "$tmp/linkdest/x-work" ]]; then fail 'mixed unlink removed a repo link'; fi
if [[ ! -L "$tmp/linkdest/x-architect" ]]; then fail 'mixed unlink removed a foreign link'; fi
if [[ ! -f "$tmp/linkdest/x-why" ]]; then fail 'mixed unlink removed a plain file'; fi

printf 'test-install: passed\n'
