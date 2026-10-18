#!/usr/bin/env bash
set -euo pipefail
fail() { printf 'test-install-v3: %s\n' "$1" >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
INSTALL="$ROOT/skills/x-rail/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
bash "$INSTALL" --home "$tmp" --dry-run >"$tmp/dry.txt"
[[ ! -e "$tmp/.pi" ]] || { printf 'dry-run created files\n' >&2; exit 1; }
grep -q '软链' "$tmp/dry.txt"
bash "$INSTALL" --home "$tmp" >"$tmp/apply.txt"
[[ -L "$tmp/.pi/agent/skills/x-rail" ]] || fail '缺少 x-rail 技能软链'
[[ -L "$tmp/.pi/agent/skills/x-handoff" ]] || fail '缺少 x-handoff 技能软链'
[[ -L "$tmp/.pi/agent/skills/x-worktree" ]] || fail '缺少 x-worktree 技能软链'
[[ -L "$tmp/.pi/agent/skills/x-self-check" ]] || fail '缺少 x-self-check 技能软链'
[[ -f "$tmp/.pi/agent/extensions/x-rail/x-failover.ts" ]] || fail '缺少 x-failover 扩展'
[[ -f "$tmp/.pi/agent/extensions/x-rail/file-io.ts" ]] || fail '缺少扩展文件写入模块'
[[ -f "$tmp/.pi/agent/extensions/x-rail/x-run-guard.ts" ]] || fail '缺少内部 guard 模块'
manifest="$(cat "$tmp/.pi/agent/extensions/x-rail/package.json")"
[[ "$manifest" == *'"./x-failover.ts"'* ]] || fail '清单缺少单一入口'
[[ "$manifest" != *'"./x-run-guard.ts"'* ]] || fail '清单仍加载第二入口'
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
