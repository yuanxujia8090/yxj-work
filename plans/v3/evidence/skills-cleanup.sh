#!/usr/bin/env bash
# =============================================================================
# x-rail v3 / 07-本机技能清理方案 —— pi 本机技能清理脚本
#
#   只归档、不删除；可重复执行；先备份再动手。
#   批次 A（默认）：全局技能之间的重复 / 断链 / 相似。
#   批次 B：被 x-rail v3 取代的全局技能（规则：x-rail 有相似技能时，删掉全局那份）。
#           有守卫：x-rail v3 不在 pi 会加载的目录中时，拒绝执行。
#
#   用法：
#     bash skills-cleanup.sh --dry-run            # 只打印计划，不做任何改动
#     bash skills-cleanup.sh                      # 执行批次 A + 仅手动(frontmatter)
#     bash skills-cleanup.sh --batch B            # 执行批次 B（x-rail v3 安装并验证后）
#     bash skills-cleanup.sh --batch B --xrail-path ~/.pi/agent/skills/x-rail   # 指定 x-rail 位置
#     bash skills-cleanup.sh --batch B --xrail-marker stages/execute.md       # 指定 v3 标志文件
#     bash skills-cleanup.sh --batch all          # A + B
#     bash skills-cleanup.sh --allow-repo-edit    # 允许改 git 仓库内的 SKILL.md（如 pr）
#     bash skills-cleanup.sh --no-manual          # 不做“仅手动”frontmatter 修改
#
#   兼容 macOS 自带 bash 3.2（不用关联数组 / mapfile / sed -i）。
# =============================================================================
set -euo pipefail

DRY=0
BATCH="A"
XRAIL_PATH=""                       # 默认：自动在 ~/.pi/agent/skills/x-rail* 中查找
XRAIL_MARKER="stages/execute.md"    # x-rail v3 的标志文件（03 §12 的阶段卡）
ALLOW_REPO_EDIT=0
DO_MANUAL=1

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --batch) shift; BATCH="${1:-A}" ;;
    --allow-repo-edit) ALLOW_REPO_EDIT=1 ;;
    --no-manual) DO_MANUAL=0 ;;
    --xrail-path) shift; XRAIL_PATH="${1:-}" ;;
    --xrail-marker) shift; XRAIL_MARKER="${1:-}" ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$BATCH" in A|B|all) ;; *) echo "--batch 只能是 A / B / all" >&2; exit 2 ;; esac

DATE="$(date +%Y-%m-%d)"
NOW="$(date '+%Y-%m-%d %H:%M:%S %z')"
PI_SKILLS="$HOME/.pi/agent/skills"
AG_SKILLS="$HOME/.agents/skills"
PI_HOME_SKILLS="$HOME/.pi/skills"
DISABLED="$HOME/.pi/agent/skills-disabled"
DEST="$DISABLED/cleanup-$DATE"
README="$DISABLED/README.md"
BACKUP_DIR="$HOME/ori-review"
BACKUP="$BACKUP_DIR/skills-backup-$DATE.tgz"
FM_BACKUP="$BACKUP_DIR/skills-frontmatter-$DATE"

# ---- 决策清单（与 07-本机技能清理方案.md 的表格一致）-------------------------
# 格式：名称|批次|原因|批次 B 额外要求已安装的 x-rail 配套技能（逗号分隔，可空）
ARCHIVE_LIST="
brainstorming|A|与 grilling / deep-think 重复；描述写“You MUST use this before any creative work”，强制触发|
using-superpowers|A|superpowers 元技能，要求“先调用技能”，是规则竞争的源头（2 周内 70 次读取）|
test-driven-development|A|与 skills-main 的 tdd 重复（x-rail 调用 tdd，保留 tdd）|
systematic-debugging|A|与 diagnosing-bugs 重复（x-rail 调用 diagnosing-bugs，保留它）|
writing-skills|A|与 writing-for-agents 重复，只保留 writing-for-agents|
design-taste-frontend-v1|A|design-taste-frontend 的旧版本，只保留新版|
image-to-code|A|与 imagegen-frontend-web 同源且相似，且是为 Codex 写的|
redesign-existing-projects|A|与 design-taste-frontend 重复（后者已覆盖 redesign 审计）|
claude-handoff|A|与 handoff 重复，且是 Claude 专用（in-progress）|
hallmark|A|断链：软链目标不存在|
receiving-code-review|A|断链：软链目标不存在|
requesting-code-review|A|断链：软链目标不存在|
writing-plans|B|x-rail v3 Plan 阶段（units.tsv、竖切、deps）取代|
executing-plans|B|x-rail v3 Execute 循环（xr next/verify/done）取代|
subagent-driven-development|B|x-rail v3 子代理驱动执行（03 §10）取代|
dispatching-parallel-agents|B|x-rail v3 并行派发规则（并发 5/2、文件集不相交）取代|
verification-before-completion|B|x-rail v3 验证门（ledger + Land 集成验证）取代|
finishing-a-development-branch|B|x-rail v3 Land 阶段（集成验证、wip 提交、交付 brief）取代|
implement|B|x-rail v3 Execute（tdd + code-review + 提交）取代|
implement-spec|B|x-rail v3 子代理驱动执行（任务图、frontier、worktree、合并队列）取代|
retro|B|x-rail v3 Reflect 步骤与 x-self-check 取代|x-self-check
handoff|B|x-rail v3 胶囊/handoff.md 与 x-handoff 取代|x-handoff
using-git-worktrees|B|x-rail v3 每单元 worktree（xr）与 x-worktree 取代|x-worktree
"

# 格式：名称|原因
MANUAL_LIST="
full-output-enforcement|描述过宽（任何需要完整输出的任务），2 周内 0 次使用；保留为手动 /skill:full-output-enforcement
prompt-optimizer|用户都是手动 /skill: 调用（3 次），不需要模型自动触发
skill-creator|与 writing-for-agents 部分相似；创建技能属低频操作，改为手动
pr|会对外开 PR（外发动作），x-rail 禁止自动对外发布；改为手动
"

# ---- 工具函数 ------------------------------------------------------------------
say()  { printf '%s\n' "$*"; }
run()  { if [ "$DRY" -eq 1 ]; then say "  [dry-run] $*"; else "$@"; fi; }
realpath_py() { python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$1"; }
exists_any() { [ -e "$1" ] || [ -L "$1" ]; }   # 断链也算存在
tildify() { case "$1" in "$HOME"/*) printf '~%s' "${1#"$HOME"}" ;; *) printf '%s' "$1" ;; esac; }       # 用于显示
homevar() { case "$1" in "$HOME"/*) printf '$HOME%s' "${1#"$HOME"}" ;; *) printf '%s' "$1" ;; esac; }   # 用于恢复命令

in_batch() {
  case "$BATCH" in
    all) return 0 ;;
    *) [ "$1" = "$BATCH" ] ;;
  esac
}

N_MOVED=0; N_ALREADY=0; N_ABSENT=0; N_CONFLICT=0; N_SKIP_REQ=0
N_MANUAL=0; N_MANUAL_ALREADY=0; N_MANUAL_SKIP=0
MOVED_ROWS=""      # README 表格行
RESTORE_CMDS=""    # 恢复命令
MANUAL_ROWS=""
MANUAL_RESTORE=""

say "== pi 技能清理  $NOW"
say "   模式: $([ $DRY -eq 1 ] && echo 'dry-run（不改动）' || echo '执行')   批次: $BATCH   仅手动: $([ $DO_MANUAL -eq 1 ] && echo 开 || echo 关)"
if pgrep -x pi >/dev/null 2>&1; then
  say "   注意：检测到 pi 正在运行；完成后请重启会话，变更才会生效。"
fi

# ---- (a) 备份 ------------------------------------------------------------------
say ""
say "== (a) 备份 -> $BACKUP"
if [ -f "$BACKUP" ]; then
  say "   已存在今天的备份，跳过（保留的是首次运行前的状态）。"
else
  TARGETS=""
  for d in .pi/agent/skills .agents/skills .pi/skills .pi/agent/skills-disabled/README.md; do
    if exists_any "$HOME/$d"; then TARGETS="$TARGETS $d"; fi
  done
  run mkdir -p "$BACKUP_DIR"
  # 不加 -h：软链按软链本身打包，不跟随到目标
  # shellcheck disable=SC2086
  run tar -czf "$BACKUP" -C "$HOME" $TARGETS
  [ "$DRY" -eq 1 ] || say "   完成：$(du -h "$BACKUP" | cut -f1)  内容:$TARGETS"
fi

# ---- 批次 B 守卫：x-rail v3 必须已在 pi 会加载的目录中 ---------------------------
XRAIL_OK=0
if [ "$BATCH" = "B" ] || [ "$BATCH" = "all" ]; then
  say ""
  say "== 批次 B 守卫：检查 x-rail v3 是否已安装在 pi 会加载的目录"
  cand=""
  if [ -n "$XRAIL_PATH" ]; then
    cand="$XRAIL_PATH"
  else
    for c in "$PI_SKILLS"/x-rail "$PI_SKILLS"/x-rail*; do
      if [ -f "$c/SKILL.md" ]; then cand="$c"; break; fi
    done
  fi
  if [ -z "$cand" ] || [ ! -f "$cand/SKILL.md" ]; then
    say "   ✗ 未找到 x-rail（期望 ${PI_SKILLS}/x-rail/SKILL.md，或用 --xrail-path 指定）"
  else
    case "$cand" in
      "$PI_SKILLS"/*|"$AG_SKILLS"/*) loaded=1 ;;
      *) loaded=0 ;;
    esac
    if [ "$loaded" -ne 1 ]; then
      say "   ✗ ${cand} 不在 pi 会加载的目录（${PI_SKILLS} 或 ${AG_SKILLS}）"
    elif ! grep -Eq '^name:[[:space:]]*x-rail[[:space:]]*$' "$cand/SKILL.md"; then
      say "   ✗ ${cand}/SKILL.md 的 name 不是 x-rail"
    elif [ ! -f "$cand/$XRAIL_MARKER" ]; then
      say "   ✗ 缺少 v3 标志文件 ${cand}/${XRAIL_MARKER}（这不是 x-rail v3）"
    else
      XRAIL_OK=1
      say "   ✓ x-rail v3：${cand}"
      if grep -Eq '^disable-model-invocation:[[:space:]]*true' "$cand/SKILL.md"; then
        say "   ! 注意：x-rail 设置了 disable-model-invocation: true，模型不会自动选用它；取代自动触发的全局技能前，建议先去掉"
      fi
    fi
  fi
  if [ "$XRAIL_OK" -ne 1 ]; then
    if [ "$DRY" -eq 1 ]; then
      XRAIL_OK=2   # 仅预览
      say "   守卫未通过；dry-run 下只预览批次 B 计划。真实执行会被拒绝。"
    else
      say "   拒绝执行批次 B。请先安装并验证 x-rail v3（06 P5.9），再重试。"
      if [ "$BATCH" = "B" ]; then exit 3; fi
      say "   （--batch all：只执行批次 A 部分）"
    fi
  fi
fi

# ---- (b) 归档（移动软链本身，不动目标）-------------------------------------------
say ""
say "== (b) 归档到 $DEST"
archive_one() {   # $1=名称 $2=源根目录 $3=子目录名 $4=原因
  local name="$1" root="$2" sub="$3" reason="$4"
  local src="$root/$name" dst="$DEST/$sub/$name" kind target
  if exists_any "$src"; then
    if exists_any "$dst"; then
      say "   ! 冲突：$dst 已存在，跳过 $src"; N_CONFLICT=$((N_CONFLICT+1)); return 0
    fi
    if [ -L "$src" ]; then target="$(readlink "$src")"; kind="软链 → $target"; else kind="目录"; fi
    say "   → $src  ($kind)"
    run mkdir -p "$DEST/$sub"
    run mv -- "$src" "$dst"          # 源路径不带结尾斜杠：mv 移动的是软链本身
    N_MOVED=$((N_MOVED+1))
    MOVED_ROWS="$MOVED_ROWS| \`$name\` | \`$(tildify "$src")\` | \`$(tildify "$dst")\` | $kind | $reason |
"
    RESTORE_CMDS="${RESTORE_CMDS}mv \"$(homevar "$dst")\" \"$(homevar "$src")\"
"
  else
    if exists_any "$dst"; then
      say "   = 已归档：$name ($sub)"; N_ALREADY=$((N_ALREADY+1))
    else
      N_ABSENT=$((N_ABSENT+1))
    fi
  fi
}

# 用 here-doc 喂循环（不用管道），这样循环里累加的计数器不会丢在子 shell 里
while IFS='|' read -r name batch reason requires; do
  [ -n "$name" ] || continue
  in_batch "$batch" || continue
  if [ "$batch" = "B" ]; then
    [ "$XRAIL_OK" -ge 1 ] || continue
    missing=""
    if [ -n "$requires" ]; then
      oldifs="$IFS"; IFS=','
      for r in $requires; do
        [ -f "$PI_SKILLS/$r/SKILL.md" ] || missing="${missing} ${r}"
      done
      IFS="$oldifs"
    fi
    if [ -n "$missing" ]; then
      say "   - 跳过 ${name}：需要的 x-rail 配套技能未安装：${missing}"
      N_SKIP_REQ=$((N_SKIP_REQ+1)); continue
    fi
  fi
  # 先移 ~/.agents/skills 里的实体目录，再移 ~/.pi/agent/skills 里的软链；
  # 恢复命令按相同顺序写出（先恢复目录，再恢复软链）
  archive_one "$name" "$AG_SKILLS" "agents-skills" "$reason"
  archive_one "$name" "$PI_SKILLS" "pi-agent-skills" "$reason"
done <<LIST
$ARCHIVE_LIST
LIST

# ---- 仅手动：给 SKILL.md 加 disable-model-invocation: true ------------------------
if [ "$DO_MANUAL" -eq 1 ] && { [ "$BATCH" = "A" ] || [ "$BATCH" = "all" ]; }; then
  say ""
  say "== 仅手动（disable-model-invocation: true）"
  while IFS='|' read -r name reason; do
    [ -n "$name" ] || continue
    f=""
    for root in "$PI_SKILLS" "$AG_SKILLS"; do
      if [ -f "$root/$name/SKILL.md" ]; then f="$root/$name/SKILL.md"; break; fi
    done
    if [ -z "$f" ]; then say "   - 未找到 ${name}，跳过"; N_MANUAL_SKIP=$((N_MANUAL_SKIP+1)); continue; fi
    real="$(realpath_py "$f")"
    if grep -Eq '^disable-model-invocation:[[:space:]]*true' "$real"; then
      say "   = 已是仅手动：$name"; N_MANUAL_ALREADY=$((N_MANUAL_ALREADY+1)); continue
    fi
    if [ "$(head -n 1 "$real")" != "---" ]; then
      say "   ! $name 的 SKILL.md 首行不是 '---'，跳过"; N_MANUAL_SKIP=$((N_MANUAL_SKIP+1)); continue
    fi
    if git -C "$(dirname "$real")" rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ "$ALLOW_REPO_EDIT" -ne 1 ]; then
      say "   ! $name 位于 git 仓库内（${real}），默认不改；需要时加 --allow-repo-edit"
      N_MANUAL_SKIP=$((N_MANUAL_SKIP+1)); continue
    fi
    say "   → $name  ($real)"
    run mkdir -p "$FM_BACKUP"
    if [ ! -f "$FM_BACKUP/$name.SKILL.md" ]; then run cp -p "$real" "$FM_BACKUP/$name.SKILL.md"; fi
    if [ "$DRY" -eq 0 ]; then
      tmp="$(mktemp)"
      awk 'NR==1{print; print "disable-model-invocation: true"; next} {print}' "$real" > "$tmp"
      cat "$tmp" > "$real"     # 用重定向写回，保留原文件的权限与 inode（软链不受影响）
      rm -f "$tmp"
    else
      say "  [dry-run] 在 $real 第 1 行 '---' 之后插入 disable-model-invocation: true"
    fi
    N_MANUAL=$((N_MANUAL+1))
    MANUAL_ROWS="$MANUAL_ROWS| \`$name\` | \`$(tildify "$real")\` | $reason |
"
    MANUAL_RESTORE="${MANUAL_RESTORE}cp -p \"$(homevar "$FM_BACKUP")/$name.SKILL.md\" \"$(homevar "$real")\"
"
  done <<LIST
$MANUAL_LIST
LIST
fi

# ---- (c) 追加 README（只有本次确有改动时才追加，保证可重复执行）---------------------
say ""
say "== (c) 记录到 $README"
if [ "$DRY" -eq 1 ]; then
  say "   [dry-run] 不写 README"
elif [ "$N_MOVED" -eq 0 ] && [ "$N_MANUAL" -eq 0 ]; then
  say "   本次没有新改动，不追加"
else
  if [ ! -f "$README" ]; then
    mkdir -p "$DISABLED"
    printf '# 已禁用的技能（归档区）\n\n本目录不在 pi 的技能扫描范围内。\n' > "$README"
  fi
  {
    printf '\n## 归档于 %s：x-rail v3 技能清理（批次 %s）\n\n' "$NOW" "$BATCH"
    printf '规则：批次 A 处理全局技能之间的重复、断链、相似；批次 B 处理被 x-rail v3 取代的全局技能（x-rail 是唯一来源）。\n'
    printf 'x-rail 实际调用的全局技能（tdd、code-review、diagnosing-bugs、research、domain-modeling、grilling、codebase-design）保留不动。\n'
    printf '依据：`plans/v3/07-本机技能清理方案.md`。只移动、不删除；备份：`%s`。\n' "$(tildify "$BACKUP")"
    printf '软链按原样移动（相对路径软链在归档区里会显示为断链，移回原位置后自动恢复）。\n\n'
    if [ "$N_MOVED" -gt 0 ]; then
      printf '| 技能 | 原位置 | 归档位置 | 类型 | 原因 |\n|---|---|---|---|---|\n%s\n' "$MOVED_ROWS"
      printf '### 恢复（逐条执行，执行后重启 pi 会话）\n\n```bash\n%s```\n' "$RESTORE_CMDS"
    fi
    if [ "$N_MANUAL" -gt 0 ]; then
      printf '\n### 改为仅手动（disable-model-invocation: true，仍可用 /skill:名称 调用）\n\n'
      printf '| 技能 | 文件 | 原因 |\n|---|---|---|\n%s\n' "$MANUAL_ROWS"
      printf '恢复为自动触发：\n\n```bash\n%s```\n' "$MANUAL_RESTORE"
    fi
  } >> "$README"
  say "   已追加"
fi

# ---- (d) 汇总 ------------------------------------------------------------------
say ""
say "== 汇总"
say "   归档：$([ $DRY -eq 1 ] && echo 计划移动 || echo 新移动) $N_MOVED 项；已归档 $N_ALREADY 项；原本不存在 $N_ABSENT 项；冲突跳过 ${N_CONFLICT} 项；缺配套技能跳过 ${N_SKIP_REQ} 项"
say "   仅手动：$([ $DRY -eq 1 ] && echo 计划设置 || echo 新设置) $N_MANUAL 项；已是仅手动 $N_MANUAL_ALREADY 项；跳过 $N_MANUAL_SKIP 项"
if [ -d "$PI_HOME_SKILLS" ]; then
  say "   提示：$PI_HOME_SKILLS 里有 $(ls -1 "$PI_HOME_SKILLS" 2>/dev/null | wc -l | tr -d ' ') 项（openspec-*），本脚本不处理（见 07 §5）"
fi
[ "$DRY" -eq 1 ] && say "   这是 dry-run：没有做任何改动。" || say "   完成。请重启 pi 会话使变更生效。"
