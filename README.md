# yxj-work

独立的工作流 skill 仓库。源仓库是唯一事实源；安装到各客户端技能目录（如 `~/.pi/agent/skills/`、`~/.config/opencode/skills/`）的形态是副本或直达源仓库的软链。

完整使用说明（七类日常场景 + 33 个技能逐个简介）：`docs/usage-guide.html`，浏览器直接打开即可。

## 包含内容

- `yxj-work`：普通任务入口，支持 fast-answer、investigate、research、design、plan、exec、bugfix、review、ops、mixed。
- `yxj-work-long`：跨阶段、跨会话和长时间任务入口。
- `yxj-work-handoff`：在 `.work-docs/tasks/<task-id>/handoff.md` 写入可恢复交接。

`scripts/runtime-skills.txt` 是运行时清单：`install.sh` 与 `check-workflow.sh` 都认它列出的目录。清单包含 3 个入口技能与 30 个辅助技能（清单与用途见 `skills/README.md`），全部随安装一起复制到同一个技能目录。

辅助技能全部设置 `disable-model-invocation: true`，不会被任务内容自动唤起；入口技能按“参考技能”表主动读取对应文件，用户也可以主动点名调用。因为入口与辅助技能同级安装，入口里的相对读取路径 `../<技能名>/SKILL.md` 在源仓库与安装目标下都成立。

本仓库不修改、覆盖、删除或运行时依赖已有的同类旧 skill。

## 安装

安装哪些 skill 由 `scripts/runtime-skills.txt` 决定（3 个入口 + 30 个辅助技能）。在本仓库根目录运行：

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

### 软链安装（开发模式）

技能目录直连源仓库，改动或 `git pull` 立即生效，不需要更新副本：

```bash
bash scripts/install.sh --dest "$HOME/.pi/agent/skills" --link     # 安装/重建软链
bash scripts/install.sh --dest "$HOME/.pi/agent/skills" --unlink   # 卸载（只删指向本仓库的链接）
```

`--link` 拒绝接管目录、他处软链和断链（不会覆盖）；软链与复制模式互斥，切换前先手工清理旧形态。`check-workflow.sh` 对两种模式都校验。

## 使用

安装后调用：

```text
/yxj-work <任务说明>
/yxj-work-long <长任务说明>
/yxj-work-handoff <交接补充说明>
```

辅助技能不能由模型自动唤起，两种用法：入口技能在对应阶段主动读取（映射见 `skills/yxj-work/SKILL.md` 的阶段表），或用户主动点名，例如 `/yxj-why`、`/yxj-arena`。普通任务按开发、排查修复或调研链路进入阶段；长任务跨会话前必须更新 checkpoint 和 handoff，下一会话先读记录再继续。

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

## 契约、状态和证据

新任务的 `contract.md` 保留 `done_when` 摘要，并增加带编号的 `Acceptance` 验收条件。每条条件必须写 `outcome`、`verification`、`verification_type`、`layer` 和 `required`。同时写 `risk`、`risk_reason`、`review_policy`、`contract_revision`、`Decision Gates` 和 `Contract Changes`。

任务规模 `L1/L2/L3/long` 与影响风险 `low/medium/high` 分开：低风险可自动进入执行；中风险默认需要确认和只读审查；高风险需要确认和完整审查。不可逆操作、花钱、对外发布、生产变更和需求范围变化不能自动豁免。

执行前运行：

```bash
bash skills/yxj-work/scripts/check-contract.sh .work-docs/tasks/<task-id>
```

`check-contract.sh` 只检查契约结构、枚举、验收条件和风险策略关系，不判断自然语言质量。历史契约没有 `Acceptance` 时保持兼容，不强制迁移。

`state.md` 是按行记录的状态文件：除了基本字段，还要记录 `calls_since_progress`、`last_progress_at`、`budget: used/limit`、`strategy_fingerprints`。新格式任务的 `contract_revision` 和 `contract_fingerprint` 必须与契约一致，`required_verification` 必须引用 `A1` 等验收条件编号；标记 done 时必须覆盖并通过所有 `required: yes` 条件。每条 evidence 都记录 `command`、`run_at`、`result` 和相关文件的 `last_edit_at`；运行时间早于文件修改时间的证据不能支撑交付。

`check-state.sh`（随技能安装到 `skills/yxj-work/scripts/`）可验证状态文件，写 `status: done` 前必须运行并通过；`tests/fixtures/` 和 `test-fixtures.sh` 覆盖合法完成、未运行、过期证据、无进展超阈值、阻塞字段缺失和新契约关联。关键词或 grep 检查只属于 `static`（静态）证据，不能单独证明行为生效。

## 完成判定

任务只有在以下条件同时满足时才能写 `status: done`：

- 所有 required 验证项为 `passed`；
- 所有 required 子任务已结束；
- 没有未处理的越界文件；
- 所有决策门允许交付；
- 每个结论都有 evidence 指针。

`failed`、`blocked`、`not_run`、未解决决策门、in_progress required 子任务或缺少 evidence 时禁止标记 `done`。optional 项必须在契约中声明并写明跳过原因。

## 熔断

每个子任务独立计数。任一条件触发即停止当前子任务：连续 3 次 required 验证失败、60 次工具调用无进展、30 分钟无有效进展、第三方 skill 越界写入，或共同前提被证据否定。

熔断必须：停止同策略重试；在 `audit/` 记录策略、错误和证据；写 `status: blocked`、`blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；写 checkpoint/handoff；禁止父任务标记 done。L1/L2/L3 的预算分别为 60/150/400 次工具调用，L3 另有 8 小时上限；无进展熔断阈值为 L1/L2 20 次、L3/long 每子任务 60 次或 30 分钟。开工后发现真实范围将超出当前 level 预算时，在 contract 与 state 显式升级 level 并记录原因，不允许静默超支。预算耗尽写 checkpoint，不标记 done，交用户决定是否追加预算。

恢复必须先读状态、最近 checkpoint、失败策略和 evidence，验证阻塞条件已解除或采用有证据的新策略；不得重复相同失败策略。

## 更新与卸载

更新前从源仓库运行 `check-repo.sh`，再用 `install.sh --update`。卸载只删除本仓库安装、且仍带有 `.yxj-work-installed` 标记的目录（`scripts/runtime-skills.txt` 列出的全部目录）；不要删除任务目录或用户文件。

## 验收

```bash
bash scripts/check-repo.sh
tmp="$(mktemp -d)"
bash scripts/install.sh --dest "$tmp"
bash scripts/check-workflow.sh --source "$PWD" --installed "$tmp"
```

详细边界见 `docs/architecture.md` 和 `docs/file-boundary.md`。
