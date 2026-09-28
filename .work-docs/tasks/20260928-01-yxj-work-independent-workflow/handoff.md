# Handoff v3：yxj-work 独立工作流仓库

## 当前状态

- task_id：`20260928-01-yxj-work-independent-workflow`
- stage：`handoff`
- status：`done`
- 已按推荐选择：两轮安装校验，因为它能在任何删除动作前验证三个目标，避免部分更新。

## 已完成

- `scripts/install.sh` 改为两轮：先检查三个目标的覆盖、marker 和 `source=`，全部通过后才统一删除、复制和写 marker。
- `scripts/check-workflow.sh` 现在校验每个 marker 的 `source=<源仓库真实路径>` 独立整行。
- 新增 `scripts/check-state.sh`，校验 done gate、过期 evidence、无进展阈值、预算和 blocked 必填字段。
- 新增 `scripts/test-install.sh`，覆盖全新安装、默认拒绝覆盖、同源更新、异源拒绝且无部分更新、无 marker 拒绝。
- 新增 `tests/fixtures/` 和 `scripts/test-fixtures.sh`，覆盖合法 done、done 但未运行、done 但 evidence 过期、超过阈值未 blocked、blocked 缺字段和合法 blocked。
- `yxj-work`、`yxj-work-long`、README、架构和边界文档已同步进展定义、熔断阈值、预算、策略指纹、证据新鲜度、L1 轻量和 index 防重复规则。
- 新建 `.work-docs/index.md` 与任务目录 `DECISIONS.md`。
- 旧 skill 哈希基线写入 `evidence/old-skills.sha256`，共 11 个文件；与 `/tmp/yxj-work-old-skills-after.sha256` 核对全部 OK。
- 旧 `check-plan.sh` 已明确只作历史参考，不列入 required 验证。

## Fresh verification

完整原始输出：`evidence/verification-run-20260928.txt`

- `bash -n scripts/*.sh`：6 个脚本全部 `passed`。
- `bash scripts/check-repo.sh`：`check-repo: passed`。
- `bash scripts/test-install.sh`：`test-install: passed`。
- `bash scripts/test-fixtures.sh`：`fixtures: passed`。
- 临时目录安装：`install: installed ...`。
- 临时安装副本：`check-workflow: passed`。
- 当前任务状态检查：最终执行需以本交接后的最后一次 `check-state` 输出为准。
- 旧 skill 哈希：11 个文件全部 `OK`。

证据记录：`evidence/verification.md`；任务状态：`state.md`。

## 约束与未验证项

- 未提交、未推送、未创建 PR。
- 未修改 `/Users/yuanxj/.pi/agent/skills/yxj-mode/`、`yxj-mode-long/`、`yxj-handoff/`。
- 未运行生产、外部网络或消费者集成验证；当前契约未要求这些层级。
- 如果继续修改任何实现文件，当前 `done` 状态必须先改回 `active`，并重新运行所有受影响的 required verification。

## 新会话第一步

```bash
cd /Users/yuanxj/Documents/github/yxj-work
bash scripts/check-state.sh .work-docs/tasks/20260928-01-yxj-work-independent-workflow
```
