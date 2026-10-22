#!/usr/bin/env bash
# 导出两个独立产物：x-rail 技能/守卫，以及模型恢复插件。
# 只写 --dest 指定的新目录；不碰真实 HOME、不装软链、不覆盖已有目录。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST=""
DRY=0
usage() { printf 'usage: %s --dest DIR [--dry-run]\n' "$0"; }
while (($#)); do
  case "$1" in
    --dest) (($# >= 2)) || { usage >&2; exit 2; }; DEST="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ -n "$DEST" ]] || { usage >&2; exit 2; }
DEST="${DEST%/}"
if [[ -e "$DEST" ]]; then
  printf 'package: 拒绝导出到已存在的目录 %s（不覆盖、不备份）\n' "$DEST" >&2
  exit 1
fi

COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf 'uncommitted')"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

list_files() {
  local base="$1"
  (cd "$ROOT/$base" && find . \
    \( -name node_modules -o -name __pycache__ -o -name .git \) -prune -o \
    -type f ! -name '*.pyc' ! -name '.DS_Store' ! -name '*.log' \
    ! -path '*/x-failover.ts' ! -path '*/failover.test.ts' -print \
    | sed 's|^\./||' | LC_ALL=C sort)
}

digest_tree() {
  # 逐文件哈希再汇总，避免依赖 tar 的元数据差异。
  local base="$1"
  (cd "$ROOT/$base" && list_files "$base" | python3 -c '
import hashlib, sys
h = hashlib.sha256()
for line in sys.stdin:
    name = line.rstrip("\n")
    digest = hashlib.sha256(open(name, "rb").read()).hexdigest()
    h.update(f"{digest}  {name}\n".encode())
print(h.hexdigest())
')
}

assert_clean() {
  local base="$1" bad
  bad="$(list_files "$base" | grep -E '(^|/)(\.work-docs|plans|notes|sessions|auth\.json|node_modules)(/|$)|\.pyc$|(^|/)\.env|\.pem$|\.key$' || true)"
  [[ -z "$bad" ]] || { printf 'package: %s 含不该导出的文件：\n%s\n' "$base" "$bad" >&2; exit 1; }
}

XR_FILES="$(list_files skills/x-rail)"
PLUGIN_FILES="$(list_files plugins/pi-model-recovery)"
XR_DIGEST="$(digest_tree skills/x-rail)"
PLUGIN_DIGEST="$(digest_tree plugins/pi-model-recovery)"

# 两个清单必须互不包含对方路径。
overlap="$(comm -12 <(printf '%s\n' "$XR_FILES") <(printf '%s\n' "$PLUGIN_FILES") || true)"
[[ -z "$overlap" ]] || { printf 'package: 两份清单重叠：%s\n' "$overlap" >&2; exit 1; }
assert_clean skills/x-rail
assert_clean plugins/pi-model-recovery

count() { printf '%s\n' "$1" | grep -c . ; }
if ((DRY)); then
  printf 'package dry-run（未写任何文件）\n'
  printf 'dest: %s\n' "$DEST"
  printf 'commit: %s\n' "$COMMIT"
  printf 'x-rail: skills/x-rail → %s 个文件，入口 skills/x-rail/SKILL.md，tree sha256:%s\n' "$(count "$XR_FILES")" "$XR_DIGEST"
  printf 'plugin: plugins/pi-model-recovery → %s 个文件，入口 plugins/pi-model-recovery/index.ts，tree sha256:%s\n' "$(count "$PLUGIN_FILES")" "$PLUGIN_DIGEST"
  printf '交叉收录: 无\n'
  exit 0
fi

mkdir -p "$DEST/x-rail" "$DEST/model-recovery"
while IFS= read -r file; do
  mkdir -p "$DEST/x-rail/$(dirname "$file")"
  cp -p "$ROOT/skills/x-rail/$file" "$DEST/x-rail/$file"
done <<< "$XR_FILES"
while IFS= read -r file; do
  mkdir -p "$DEST/model-recovery/$(dirname "$file")"
  cp -p "$ROOT/plugins/pi-model-recovery/$file" "$DEST/model-recovery/$file"
done <<< "$PLUGIN_FILES"

manifest() {
  local name="$1" entry="$2" tree="$3" files="$4" out="$DEST/$1/manifest.json"
  {
    printf '{\n  "schema": 1,\n  "product": "%s",\n  "entry": "%s",\n  "source_commit": "%s",\n  "exported_at": "%s",\n  "tree_digest": "sha256:%s",\n  "files": [\n' "$name" "$entry" "$COMMIT" "$TS" "$tree"
    printf '%s\n' "$files" | awk 'BEGIN{first=1} {if(!first) printf ",\n"; printf "    \"%s\"", $0; first=0} END{printf "\n"}'
    printf '  ]\n}\n'
  } > "$out"
}
manifest x-rail SKILL.md "$XR_DIGEST" "$XR_FILES"
manifest model-recovery index.ts "$PLUGIN_DIGEST" "$PLUGIN_FILES"

printf 'package: 已导出到 %s\n' "$DEST"
printf '  x-rail: %s 个文件，tree sha256:%s\n' "$(count "$XR_FILES")" "$XR_DIGEST"
printf '  model-recovery: %s 个文件，tree sha256:%s\n' "$(count "$PLUGIN_FILES")" "$PLUGIN_DIGEST"
printf '  commit: %s\n' "$COMMIT"
