#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
INSTALL="$ROOT/skills/x-rail/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
bash "$INSTALL" --home "$tmp" --dry-run >"$tmp/dry.txt"
[[ ! -e "$tmp/.pi" ]] || { printf 'dry-run created files\n' >&2; exit 1; }
grep -q '软链' "$tmp/dry.txt"
bash "$INSTALL" --home "$tmp" >"$tmp/apply.txt"
[[ -L "$tmp/.pi/agent/skills/x-rail" ]]
[[ -L "$tmp/.pi/agent/skills/x-handoff" ]]
[[ -L "$tmp/.pi/agent/skills/x-worktree" ]]
[[ -L "$tmp/.pi/agent/skills/x-self-check" ]]
[[ -f "$tmp/.pi/agent/extensions/x-failover.ts" ]]
[[ -f "$tmp/.pi/agent/extensions/x-run-guard.ts" ]]
bash "$INSTALL" --home "$tmp" >"$tmp/again.txt"
grep -q '已是目标软链' "$tmp/again.txt"
grep -q '扩展未变化' "$tmp/again.txt"
mkdir -p "$tmp/.pi/agent/skills"
rm "$tmp/.pi/agent/skills/x-handoff"
printf 'old\n' >"$tmp/.pi/agent/skills/x-handoff"
bash "$INSTALL" --home "$tmp" >"$tmp/backup.txt"
[[ -L "$tmp/.pi/agent/skills/x-handoff" ]]
grep -q '备份' "$tmp/backup.txt"
find "$tmp/.pi/agent" -type d -name 'v3-backup-*' | grep -q .
printf 'test-install-v3: passed\n'
