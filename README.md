# yxj-work

独立的 Pi 工作流 skill 仓库。源仓库是唯一事实源；安装到 `~/.pi/agent/skills/` 的目录只是运行副本。

## 包含内容

- `yxj-work`：普通任务入口，支持 fast-answer、investigate、research、design、plan、exec、bugfix、review、ops、mixed。
- `yxj-work-long`：跨阶段、跨会话和长时间任务入口。
- `yxj-work-handoff`：在 `.work-docs/tasks/<task-id>/handoff.md` 写入可恢复交接。

`scripts/runtime-skills.txt` 是运行时清单：`install.sh` 与 `check-workflow.sh` 都只认它列出的目录。`skills/` 下其余目录（27 个外部 skill，见 `skills/README.md`）是仓库素材，不参与安装与一致性校验。

本仓库不修改、覆盖、删除或运行时依赖已有的同类旧 skill。

## 安装

安装哪些 skill 由 `scripts/runtime-skills.txt` 决定（默认三个自研入口）。在本仓库根目录运行：

```bash
bash scripts/check-repo.sh
bash scripts/install.sh --dest "$HOME/.pi/agent/skills"
```

安装脚本默认拒绝覆盖已有目录。仅当目标目录包含本仓库写入的 `.yxj-work-installed` 标记时，才允许使用：

```bash
bash scripts/install.sh --dest "$HOME/.pi/agent/skills" --update
```

安装后检查：

```bash
bash scripts/check-workflow.sh \
  --source "$PWD" \
  --installed "$HOME/.pi/agent/skills"
```

## 使用

安装后调用：

```text
/yxj-work <任务说明>
/yxj-work-long <长任务说明>
/yxj-work-handoff <交接补充说明>
```

`fast-answer` 不创建工作目录。L1/L2/L3 任务以命令实际执行目录为根，创建唯一：

```text
.work-docs/
└── tasks/<task-id>/
    ├── contract.md
    ├── state.md
    ├── handoff.md
    ├── evidence/
    ├── outputs/
    ├── audit/
    └── tmp/
```

`<task-id>` 是目录名，格式 `{YYYYMMDD}-{NN}-{slug}`（例 `20260928-01-yxj-work-independent-workflow`）：日期为创建当天，`{NN}` 为当日内两位自增序号（不回收空号），`{slug}` 为任务短名。取号与续用规则见 `docs/file-boundary.md`。

所有工作流持久文件必须位于 `.work-docs/`。用户明确指定的项目代码是任务目标，不伪装成工作流文档；第三方 skill 的报告、日志、缓存、下载和中间文件必须能指定到任务目录，否则隔离或阻塞。

## 状态、进展和证据新鲜度

`state.md` 是按行记录的状态文件：除了基本字段，还要记录 `calls_since_progress`、`last_progress_at`、`budget: used/limit`、`strategy_fingerprints`。有效进展只指新增 done_when 证据，或 required 验证从失败/未运行变为通过。每条 evidence 都记录 `command`、`run_at`、`result` 和相关文件的 `last_edit_at`；运行时间早于文件修改时间的证据不能支撑交付。新任务先读 `.work-docs/index.md`，相同范围的进行中任务直接续接。

`check-state.sh` 可验证状态文件；`tests/fixtures/` 和 `test-fixtures.sh` 覆盖合法完成、未运行、过期证据、无进展超阈值和阻塞字段缺失。关键词或 grep 检查只属于 `static`（静态）证据，不能单独证明行为生效。

## 完成判定

任务只有在以下条件同时满足时才能写 `status: done`：

- 所有 required 验证项为 `passed`；
- 所有 required 子任务已结束；
- 没有未处理的越界文件；
- 所有决策门允许交付；
- 每个结论都有 evidence 指针。

`failed`、`blocked`、`not_run`、未解决决策门、active required 子任务或缺少 evidence 时禁止标记 `done`。optional 项必须在契约中声明并写明跳过原因。

## 熔断

每个子任务独立计数。任一条件触发即停止当前子任务：连续 3 次 required 验证失败、60 次工具调用无进展、30 分钟无有效进展、第三方 skill 越界写入，或共同前提被证据否定。

熔断必须：停止同策略重试；在 `audit/` 记录策略、错误和证据；写 `status: blocked`、`blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；写 checkpoint/handoff；禁止父任务标记 done。默认长任务预算为单子任务 60 次工具调用或 30 分钟无进展、全任务 400 次工具调用或 8 小时；预算耗尽写 checkpoint，不标记 done。

恢复必须先读状态、最近 checkpoint、失败策略和 evidence，验证阻塞条件已解除或采用有证据的新策略；不得重复相同失败策略。

## 更新与卸载

更新前从源仓库运行 `check-repo.sh`，再用 `install.sh --update`。卸载只删除本仓库安装并且仍带有 `.yxj-work-installed` 标记的三个目录；不要删除任务目录或用户文件。

## 验收

```bash
bash scripts/check-repo.sh
bash scripts/install.sh --dest "$(mktemp -d)"
bash scripts/check-workflow.sh --source "$PWD" --installed <临时目录>
```

详细边界见 `docs/architecture.md` 和 `docs/file-boundary.md`。
