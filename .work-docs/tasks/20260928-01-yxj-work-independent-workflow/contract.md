# Contract

- task_id: `20260928-01-yxj-work-independent-workflow`
- scope: 完成 `/Users/yuanxj/Documents/github/yxj-work` 独立工作流仓库，并与旧 `yxj-mode` 体系隔离。
- allowed: 只修改本仓库；工作流持久文件写入本仓库 `.work-docs/` 任务目录。
- forbidden: 不修改、移动、删除、重命名 `/Users/yuanxj/.pi/agent/skills/yxj-mode/`、`yxj-mode-long/`、`yxj-handoff/`；不提交、推送或创建 PR；不写入外部 `.audit/`、`00-Inbox/`、Wiki、项目 docs 或仓库根目录工作流文件。

## Done when

1. 新仓库包含 `yxj-work`、`yxj-work-long`、`yxj-work-handoff`、playbooks、README、架构和边界说明。
2. 安装默认拒绝覆盖；`--update` 只更新带合法 `source=` marker 且来源相同的副本；拒绝发生前不产生部分更新。
3. 状态格式、进展定义、无进展熔断、预算、策略指纹、证据新鲜度、防重复和 L1 轻量规则已写入运行 skill 与文档。
4. `check-state.sh`、安装行为测试、状态 fixture 可运行并覆盖契约要求的通过与拒绝场景。
5. 源仓库检查、临时安装、副本一致性和全部 required 验证通过。
6. 三个旧 skill 的完整性哈希与 `/tmp` 既有清单一致；本轮基线保存到任务 evidence。

## Required verification

- `bash -n scripts/*.sh`：`syntax/config`，结果写入 `evidence/verification.md`。
- `bash scripts/check-repo.sh`：`static`，结果写入 `evidence/verification.md`。
- `bash scripts/test-install.sh`：`runtime/local`，结果写入 `evidence/verification.md`。
- `bash scripts/test-fixtures.sh`：`runtime/local`，结果写入 `evidence/verification.md`。
- 临时目录 `install.sh` + `check-workflow.sh`：`runtime/local`，结果写入 `evidence/verification.md`。
- `bash scripts/check-state.sh <本任务目录>`：`static`，结果写入 `evidence/verification.md`。
- `shasum -a 256 -c evidence/old-skills.sha256`：`external`，只读旧 skill，结果写入 `evidence/verification.md`。

旧 `~/.pi/agent/skills/yxj-mode/scripts/check-plan.sh` 仅作历史参考，不属于 required verification。
