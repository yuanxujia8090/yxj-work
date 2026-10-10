#!/usr/bin/env bash
# 在目标项目里创建分支工作区，并复制主分支目录的 .env.local。
# 用法: create_worktree.sh [NAME] [--main BRANCH] [--dir DIR]
# 退出码: 0 成功; 1 分支或目录已存在; 2 参数、环境或 git 操作错误。
set -euo pipefail

PROG="${0##*/}"
usage() { printf 'usage: %s [NAME] [--main BRANCH] [--dir DIR]\n' "$PROG" >&2; }
fail() { printf '%s: %s\n' "$PROG" "$1" >&2; exit "$2"; }

NAME=""
MAIN=""
DIR=".worktrees"
while (($#)); do
  case "$1" in
    --main) (($# >= 2)) || fail "--main needs a value" 2; MAIN="$2"; shift 2 ;;
    --dir) (($# >= 2)) || fail "--dir needs a value" 2; DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -*) usage; fail "unknown option: $1" 2 ;;
    *) [[ -z "$NAME" ]] || { usage; fail "only one name is accepted" 2; }; NAME="$1"; shift ;;
  esac
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a git repository" 2
# 新工作区固定建在主工作区（git worktree list 的第一条）下，避免嵌套在其他工作区里；
# 从子工作区运行时也回到主工作区的 .worktrees。
PRIMARY="$(git worktree list --porcelain | awk '/^worktree / { print substr($0, 10); exit }')"
ROOT="${PRIMARY:-$(git rev-parse --show-toplevel)}"

[[ -n "$NAME" ]] || NAME="feat-$(date +%Y%m%d%H%M%S)"
case "$DIR" in /*) fail "--dir must be relative to the repository root" 2 ;; esac
# 名称既是分支名也是目录名，所以既要是合法引用名，也不能带路径分隔或上跳。
git check-ref-format --branch "$NAME" >/dev/null 2>&1 || fail "invalid name: $NAME" 2
case "$NAME" in */*|*..*|.*|*/) fail "name must not contain '/', '..' or a leading dot: $NAME" 2 ;; esac

detect_main() {
  local candidate head
  for candidate in main master; do
    if git show-ref --verify --quiet "refs/heads/$candidate"; then printf '%s\n' "$candidate"; return 0; fi
  done
  head="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  if [[ -n "$head" ]]; then printf '%s\n' "${head#origin/}"; return 0; fi
  return 1
}

if [[ -z "$MAIN" ]]; then
  MAIN="$(detect_main)" || fail "cannot find main or master; pass --main BRANCH" 2
fi
git rev-parse --verify --quiet "$MAIN^{commit}" >/dev/null || fail "unknown base branch: $MAIN" 2

git show-ref --verify --quiet "refs/heads/$NAME" && fail "branch already exists: $NAME" 1
TARGET="$ROOT/$DIR/$NAME"
[[ -e "$TARGET" ]] && fail "path already exists: $TARGET" 1

mkdir -p "$ROOT/$DIR"
git worktree add -b "$NAME" "$TARGET" "$MAIN" >&2

# .env.local 从签出主分支的那个工作区复制，找不到就用仓库根目录。
SOURCE_DIR="$(git worktree list --porcelain | awk -v want="refs/heads/$MAIN" '
  /^worktree / { dir = substr($0, 10) }
  /^branch / { if ($2 == want) print dir }' | head -1)"
[[ -n "$SOURCE_DIR" ]] || SOURCE_DIR="$ROOT"

ENV_STATUS="源文件不存在，跳过"
if [[ -f "$SOURCE_DIR/.env.local" ]]; then
  cp "$SOURCE_DIR/.env.local" "$TARGET/.env.local"
  ENV_STATUS="已复制自 $SOURCE_DIR/.env.local"
fi

BASE="$(git -C "$TARGET" rev-parse --short HEAD)"
printf 'worktree: %s\n' "$TARGET"
printf 'branch:   %s (基点 %s, 来自 %s)\n' "$NAME" "$BASE" "$MAIN"
printf 'env:      .env.local %s\n' "$ENV_STATUS"
if ! git -C "$ROOT" check-ignore -q "$TARGET" 2>/dev/null; then
  printf 'note:     %s/%s 没有被 .gitignore 忽略，主工作区的 git status 会看到它\n' "$DIR" "$NAME"
fi
