#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { printf 'test-flow: %s\n' "$1" >&2; exit 1; }
need_text() {
  local file="$1" pattern="$2"
  grep -Fq -- "$pattern" "$ROOT/$file" || fail "missing '$pattern' in $file"
}

# Each common task shape must expose a complete route, not only a stage name.
need_text skills/x-rail/SKILL.md '开发：`design → plan → exec → review`'
need_text skills/x-rail/SKILL.md '问题排查与修复：`investigate → bugfix → review`'
need_text skills/x-rail/SKILL.md '调研：`research → decision gate`'
need_text skills/x-rail/SKILL.md '| exec | `playbooks/exec.md` |'
need_text skills/x-rail/SKILL.md '| bugfix | `playbooks/bugfix.md` |'
need_text skills/x-rail/SKILL.md '| research | `playbooks/research.md` |'

# Development keeps design, plan, execution and review as separate verifiable units.
need_text skills/x-rail/playbooks/design.md 'Acceptance'
need_text skills/x-rail/playbooks/design.md 'check-contract.sh'
need_text skills/x-rail/playbooks/plan.md 'Acceptance'
need_text skills/x-rail/playbooks/exec.md 'contract_revision'
need_text skills/x-rail/playbooks/review.md 'review_policy'
need_text skills/x-rail/SKILL.md '正式阶段先建任务骨架'
need_text skills/x-rail/SKILL.md '断言驱动读取'
need_text skills/x-rail/SKILL.md '超时恢复'
need_text skills/x-rail/SKILL.md '固定收尾顺序'
need_text skills/x-rail/playbooks/review.md '轻量 review'
need_text skills/x-rail/playbooks/review.md '先列断言，再按断言读取局部实现'
need_text skills/x-rail/playbooks/investigate.md 'create the task skeleton and minimal contract'
need_text skills/x-rail/playbooks/research.md 'create the task skeleton and minimal contract'
need_text skills/x-rail/playbooks/plan.md 'create the task skeleton and minimal contract'
need_text skills/x-rail/playbooks/exec.md 'create the task skeleton and minimal contract'
need_text skills/x-rail/playbooks/plan.md 'Split work into independently verifiable tasks'
need_text skills/x-rail/playbooks/exec.md 'Verify from narrow to broad'
need_text skills/x-rail/playbooks/review.md 'Review correctness, security boundaries'

# Productized stage entry: each formal stage exposes the same human-readable contract.
for stage in investigate research design plan exec bugfix review ops mixed; do
  need_text "skills/x-rail/playbooks/$stage.md" '## 阶段入口'
  need_text "skills/x-rail/playbooks/$stage.md" '适用场景：'
  need_text "skills/x-rail/playbooks/$stage.md" '输入：'
  need_text "skills/x-rail/playbooks/$stage.md" '输出：'
  need_text "skills/x-rail/playbooks/$stage.md" '不做什么：'
  need_text "skills/x-rail/playbooks/$stage.md" '停止条件：'
done
need_text skills/x-rail/SKILL.md '## 阶段启动摘要'
need_text skills/x-rail/SKILL.md '代码层、接口层、流程层、运行层、交付层'
need_text skills/x-rail/SKILL.md '摘要不是第二套状态事实源'
for field in 当前阶段 任务 风险 允许改动 禁止动作 必过验收 已有证据 当前阻塞 下一步第一动作; do
  need_text skills/x-rail/SKILL.md "${field}："
done
need_text skills/x-rail/SKILL.md 'playbooks/verification.md'
need_text skills/x-rail/playbooks/verification.md '正确示例'
need_text skills/x-rail/playbooks/verification.md '反例'
need_text skills/x-rail-long/SKILL.md '阶段启动摘要'
need_text skills/README.md '阶段选择表'
# The user-facing stage table must cover exactly the canonical route names.
route_names="$(awk '/^## 路由$/{f=1;next} /^## /{f=0} f' "$ROOT/skills/x-rail/SKILL.md" | sed -n 's/^- `\([a-z-]*\)`.*/\1/p' | sort)"
table_names="$(awk -F '|' '/^## 阶段选择表$/{f=1;next} /^## /{f=0} f && /^\|/ {value=$3; sub(/^[[:space:]]*/, "", value); if (match(value, /^[a-z][a-z-]*/)) print substr(value, RSTART, RLENGTH)}' "$ROOT/skills/README.md" | sort)"
[[ "$route_names" == "$table_names" ]] || fail 'stage selection table differs from canonical routes'

# Lightweight document work remains a plan branch, not a new runtime stage.
need_text skills/x-rail/SKILL.md '轻量文档整理'
need_text skills/x-rail/SKILL.md '单纯读取新文件、获取环境状态不算有效进展'
need_text skills/x-rail/SKILL.md '实施计划读取'
need_text skills/x-rail/playbooks/plan.md '## 轻量文档分支'
need_text skills/x-rail/playbooks/plan.md 'templates/document-task.md'
need_text skills/x-rail/playbooks/plan.md '6 次资料工具调用'
need_text skills/x-rail/playbooks/plan.md '20 次总工具调用'
need_text skills/x-rail/playbooks/plan.md '初稿中的哪条预期结果或事实缺口'
need_text skills/x-rail/playbooks/plan.md '不是宿主自动拦截'
need_text skills/x-rail/playbooks/plan.md '必过项不能降为可选项'
need_text skills/x-rail/playbooks/plan.md '固定提交'
need_text README.md 'templates/document-task.md'
need_text docs/architecture.md '轻量文档'
need_text docs/usage-guide.html 'id="light-document"'

# Bug fixing cannot skip reproduction or lose the before/after proof.
need_text skills/x-rail/playbooks/bugfix.md 'Reproduce with expected versus actual behavior'
need_text skills/x-rail/playbooks/bugfix.md 'Preserve failing-before and passing-after evidence'

# Research must separate facts from inference and stop at its decision gate.
need_text skills/x-rail/playbooks/research.md 'Keep an evidence ledger'
need_text skills/x-rail/playbooks/research.md 'End with `decision_gate: proceed|design_only|gather_more|do_not_build`'

# A long run must leave a next-session-readable record before it pauses or crosses a day.
need_text skills/x-rail-long/SKILL.md '每个阶段结束都要追加一个 `audit/checkpoint-<序号>.md`'
need_text skills/x-rail-long/SKILL.md '并同步更新 `state.md`'
need_text skills/x-rail-long/SKILL.md '启动已有任务时，不创建新任务目录。先依次读取 `.work-docs/index.md`'
need_text skills/x-rail-long/SKILL.md '`handoff.md`'
need_text skills/x-handoff/SKILL.md '下一会话第一步'

# Skill metadata and invocation boundaries stay explicit and single-sourced.
need_text skills/README.md '技能元数据'
need_text skills/README.md '运行时清单是安装范围的唯一来源'
need_text scripts/runtime-skills.txt 'disable-model-invocation: true'
bash "$ROOT/scripts/check-skill-metadata.sh" "$ROOT" >/dev/null

# show-me-your-work is intentionally not another runtime entry.
if grep -Fxq 'show-me-your-work' "$ROOT/scripts/runtime-skills.txt"; then
  fail 'show-me-your-work must not be a second long-run entry'
fi

printf 'test-flow: passed\n'
