#!/usr/bin/env bash
# 把 x-rail v3 的 4 个技能软链和两个扩展装进某个 HOME 的 ~/.pi。
# 默认不跑。对真实 HOME 安装前请先 --dry-run。本脚本不改 models.json / settings.json，也不跑技能清理。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
DRY=0
DO_BACKUP=1
TARGET_HOME="${HOME}"

usage() {
  printf '用法: %s [--dry-run] [--home DIR] [--no-backup]\n' "$0"
}

while (($#)); do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --home) (($# >= 2)) || { usage >&2; exit 2; }; TARGET_HOME="$2"; shift 2 ;;
    --no-backup) DO_BACKUP=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

PI="$TARGET_HOME/.pi/agent"
SKILLS="$PI/skills"
# pi 会把 extensions/ 下每个 .ts 都当扩展加载，所以辅助模块放进子目录，用 package.json 的 pi 清单只声明两个入口
EXT="$PI/extensions/x-rail"
MANIFEST='{\n  "name": "x-rail-extensions",\n  "private": true,\n  "type": "module",\n  "pi": { "extensions": ["./x-failover.ts", "./x-run-guard.ts"] }\n}'
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$PI/v3-backup-$STAMP"

# macOS 自带 bash 3.2 不支持关联数组，用函数代替
link_of() { printf '%s' "$ROOT/skills/$1"; }

EXT_FILES=(
  constants.ts classify.ts breaker.ts switch.ts compat.ts failback.ts subagent.ts
  store.ts watchdog.ts guard-core.ts run-files.ts x-failover.ts x-run-guard.ts
)

note() { printf '%s\n' "$1"; }

backup_path() {
  local dest="$1"
  [[ "$DO_BACKUP" -eq 1 ]] || return 0
  mkdir -p "$BACKUP"
  mv "$dest" "$BACKUP/"
  note "备份 $dest -> $BACKUP/"
}

same_link() {
  local dest="$1" expect="$2"
  [[ -L "$dest" ]] || return 1
  local got
  got="$(readlink "$dest")"
  [[ "$got" == "$expect" ]]
}

if [[ "$DRY" -eq 1 ]]; then
  note "dry-run HOME=$TARGET_HOME"
  for name in x-rail x-handoff x-worktree x-self-check; do
    note "软链 $SKILLS/$name -> $(link_of "$name")"
  done
  for file in "${EXT_FILES[@]}"; do
    note "复制 $EXT/$file"
  done
  note "写入 $EXT/package.json（pi 清单：x-failover.ts、x-run-guard.ts）"
  note "不修改 models.json、settings.json，不运行 skills-cleanup.sh"
  exit 0
fi

mkdir -p "$SKILLS" "$EXT"
for name in x-rail x-handoff x-worktree x-self-check; do
  dest="$SKILLS/$name"
  expect="$(link_of "$name")"
  if same_link "$dest" "$expect"; then
    note "已是目标软链 $dest"
    continue
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    backup_path "$dest"
  fi
  ln -s "$expect" "$dest"
  note "已链接 $dest"
done

for file in "${EXT_FILES[@]}"; do
  src="$ROOT/skills/x-rail/extensions/$file"
  dest="$EXT/$file"
  [[ -f "$src" ]] || { printf 'install: 缺少 %s\n' "$src" >&2; exit 1; }
  if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
    note "扩展未变化 $dest"
    continue
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    backup_path "$dest"
  fi
  cp "$src" "$dest"
  note "已安装 $dest"
done

manifest_tmp="$(mktemp)"
printf '%b\n' "$MANIFEST" > "$manifest_tmp"
if [[ -f "$EXT/package.json" ]] && cmp -s "$manifest_tmp" "$EXT/package.json"; then
  rm -f "$manifest_tmp"; note "清单未变化 $EXT/package.json"
else
  [[ -e "$EXT/package.json" ]] && backup_path "$EXT/package.json"
  mv "$manifest_tmp" "$EXT/package.json"; note "已写入 $EXT/package.json"
fi

note "安装完成。配置片段在 $ROOT/skills/x-rail/config/examples/ ，需要你批准后才并入 settings。"
note "批次 B 不由本脚本执行。"
