#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-install: %s\n' "$1" >&2; exit 1; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null
bash "$ROOT/scripts/check-workflow.sh" --source "$ROOT" --installed "$tmp/fresh" >/dev/null
if bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" >/dev/null 2>&1; then fail 'no-update overwrite was accepted'; fi
bash "$ROOT/scripts/install.sh" --dest "$tmp/fresh" --update >/dev/null

mkdir "$tmp/foreign"
cp -R "$tmp/fresh"/. "$tmp/foreign"/
printf 'source=/other\ninstalled_at=old\n' > "$tmp/foreign/yxj-work-long/.yxj-work-installed"
before="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/foreign" --update >/dev/null 2>&1; then fail 'foreign source update was accepted'; fi
after="$(find "$tmp/foreign" -type f -print0 | sort -z | xargs -0 shasum -a 256)"
[[ "$before" == "$after" ]] || fail 'foreign source refusal partially changed targets'

mkdir -p "$tmp/unmarked/yxj-work"
if bash "$ROOT/scripts/install.sh" --dest "$tmp/unmarked" --update >/dev/null 2>&1; then fail 'unmarked update was accepted'; fi
printf 'test-install: passed\n'
