#!/usr/bin/env bash
# skills/x-worktree/scripts/create_worktree.sh 的回归测试：在临时仓库里真的建工作区。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SCRIPT="$ROOT/skills/x-worktree/scripts/create_worktree.sh"
[[ -f "$SCRIPT" ]] || { printf 'test-worktree: missing %s\n' "$SCRIPT" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cases=0
ok() { cases=$((cases + 1)); }
bad() { printf 'test-worktree: %s\n' "$1" >&2; exit 1; }

# 建一个临时仓库：分支名、是否放 .env.local 由参数决定。
new_repo() {
  local branch="$1" env="${2:-yes}" repo="$TMP/$1-$(date +%s%N)"
  git init -q -b "$branch" "$repo"
  printf 'hello\n' > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" -c user.email=t@example.com -c user.name=t commit -q -m init
  [[ "$env" == yes ]] && printf 'SECRET=1\n' > "$repo/.env.local"
  printf '%s\n' "$repo"
}

# 1) main 仓库：默认名称、分支、.env.local 复制
repo="$(new_repo main)"
(cd "$repo" && bash "$SCRIPT" >/dev/null)
created="$(ls "$repo/.worktrees")"
[[ "$created" =~ ^feat-[0-9]{14}$ ]] || bad "default name is not feat-{YYYYMMDDHHmmss}: $created"
[[ -d "$repo/.worktrees/$created" ]] || bad "worktree directory not created"
git -C "$repo" show-ref --verify --quiet "refs/heads/$created" || bad "branch not created"
cmp -s "$repo/.env.local" "$repo/.worktrees/$created/.env.local" || bad ".env.local not copied"
git -C "$repo" worktree list --porcelain | grep -q "$repo/.worktrees/$created" || bad "worktree not registered"
[[ ! -e "$repo/.worktrees/$created/node_modules" ]] || bad "unexpected node_modules in a non-pnpm worktree"
ok

# 2) 显式名称 + --dir 覆盖
(cd "$repo" && bash "$SCRIPT" demo --dir custom-wt >/dev/null)
[[ -d "$repo/custom-wt/demo" ]] || bad "--dir override not honored"
cmp -s "$repo/.env.local" "$repo/custom-wt/demo/.env.local" || bad ".env.local not copied with --dir"
ok

# 3) 从已有工作区里运行时：新工作区仍建在主工作区的 .worktrees 下，.env.local 仍来自主分支目录
(cd "$repo/.worktrees/$created" && bash "$SCRIPT" from-child >/dev/null)
cmp -s "$repo/.env.local" "$repo/.worktrees/from-child/.env.local" || bad "env copied from wrong worktree"
ok

# 4) 分支已存在 -> 退出 1
set +e
(cd "$repo" && bash "$SCRIPT" "$created" >/dev/null 2>&1); code=$?
set -e
[[ "$code" -eq 1 ]] || bad "duplicate branch should exit 1, got $code"
ok

# 5) 目录已存在 -> 退出 1
mkdir -p "$repo/.worktrees/taken"
set +e
(cd "$repo" && bash "$SCRIPT" taken >/dev/null 2>&1); code=$?
set -e
[[ "$code" -eq 1 ]] || bad "existing path should exit 1, got $code"
ok

# 6) 非法名称 -> 退出 2
for name in "bad name" "a/b" ".."; do
  set +e
  (cd "$repo" && bash "$SCRIPT" "$name" >/dev/null 2>&1); code=$?
  set -e
  [[ "$code" -eq 2 ]] || bad "invalid name '$name' should exit 2, got $code"
  ok
done

# 7) master 仓库：识别 master
mrepo="$(new_repo master)"
(cd "$mrepo" && bash "$SCRIPT" master-case >/dev/null)
[[ -d "$mrepo/.worktrees/master-case" ]] || bad "master repo worktree not created"
ok

# 8) 没有 main/master -> 退出 2
trepo="$(new_repo trunk)"
set +e
out="$( (cd "$trepo" && bash "$SCRIPT" nope) 2>&1 )"; code=$?
set -e
[[ "$code" -eq 2 ]] || bad "missing main branch should exit 2, got $code"
[[ "$out" == *"cannot find main or master"* ]] || bad "missing main branch message: $out"
ok

# 9) 没有 .env.local 时不失败，也不产出空文件
nrepo="$(new_repo main no)"
(cd "$nrepo" && bash "$SCRIPT" no-env >/dev/null)
[[ -d "$nrepo/.worktrees/no-env" ]] || bad "worktree not created without .env.local"
[[ ! -e "$nrepo/.worktrees/no-env/.env.local" ]] || bad "unexpected .env.local created"
ok

# 10) --main 覆盖：基点来自指定分支
(cd "$repo" && git branch other main && bash "$SCRIPT" other-case --main other >/dev/null)
[[ -d "$repo/.worktrees/other-case" ]] || bad "--main override not honored"
ok

# 11) 参数错误 -> 退出 2
set +e
(cd "$repo" && bash "$SCRIPT" a b >/dev/null 2>&1); code=$?
set -e
[[ "$code" -eq 2 ]] || bad "extra positional argument should exit 2, got $code"
ok

# 12) pnpm 项目：必须在新工作区里装依赖，node_modules 必须是真目录
prepo="$(new_repo main)"
printf '{"name":"t","packageManager":"pnpm@11"}\n' > "$prepo/package.json"
printf 'lockfileVersion: 9\n' > "$prepo/pnpm-lock.yaml"
git -C "$prepo" add package.json pnpm-lock.yaml
git -C "$prepo" -c user.email=t@example.com -c user.name=t commit -q -m pnpm
shim="$TMP/shim-real"; mkdir -p "$shim"
cat > "$shim/pnpm" <<'SHIM'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$PNPM_LOG"
mkdir -p node_modules/.pnpm-shim
SHIM
chmod +x "$shim/pnpm"
rm -f "$TMP/pnpm.log"
(cd "$prepo" && PATH="$shim:$PATH" PNPM_LOG="$TMP/pnpm.log" bash "$SCRIPT" pnpm-case >/dev/null)
[[ "$(cat "$TMP/pnpm.log" 2>/dev/null)" == "install" ]] || bad "pnpm install not invoked: $(cat "$TMP/pnpm.log" 2>/dev/null)"
[[ -d "$prepo/.worktrees/pnpm-case/node_modules/.pnpm-shim" ]] || bad "dependencies not installed in the new worktree"
[[ ! -L "$prepo/.worktrees/pnpm-case/node_modules" ]] || bad "node_modules must not be a symlink"
[[ ! -e "$prepo/node_modules" ]] || bad "install must not touch the main worktree"
ok

# 13) 有 lockfile 但 PATH 上没有 pnpm -> 退出 2，工作区保留
set +e
out="$( (cd "$prepo" && PATH=/usr/bin:/bin bash "$SCRIPT" no-pnpm) 2>&1 )"; code=$?
set -e
[[ "$code" -eq 2 ]] || bad "missing pnpm should exit 2, got $code"
[[ "$out" == *"pnpm is not on PATH"* ]] || bad "missing pnpm message: $out"
[[ -d "$prepo/.worktrees/no-pnpm" ]] || bad "worktree should stay created when pnpm is missing"
ok

# 14) 安装留下符号链接 node_modules -> 退出 1
shim2="$TMP/shim-link"; mkdir -p "$shim2"
cat > "$shim2/pnpm" <<'SHIM'
#!/usr/bin/env bash
ln -sfn /tmp node_modules
SHIM
chmod +x "$shim2/pnpm"
set +e
out="$( (cd "$prepo" && PATH="$shim2:$PATH" bash "$SCRIPT" link-case) 2>&1 )"; code=$?
set -e
[[ "$code" -eq 1 ]] || bad "symlinked node_modules should exit 1, got $code"
[[ "$out" == *"must not be a symlink"* ]] || bad "symlink message: $out"
ok

printf 'test-worktree: passed (%s cases)\n' "$cases"
