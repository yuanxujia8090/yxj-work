# yxj-work

独立的工作流 skill 仓库。源仓库是唯一事实源；安装到各客户端技能目录（如 `~/.pi/agent/skills/`、`~/.config/opencode/skills/`）的形态是副本或直达源仓库的软链。

完整使用说明（七类日常场景 + 轻量文档分支 + 33 个技能逐个简介）：`docs/usage-guide.html`，浏览器直接打开即可。

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

辅助技能不能由模型自动唤起，两种用法：入口技能在对应阶段主动读取（映射见 `skills/yxj-work/SKILL.md` 的阶段表），或用户主动点名，例如 `/yxj-why`、`/yxj-arena`。普通任务按开发、排查修复或调研链路进入阶段；正式阶段先创建任务骨架和最小契约，并通过 `check-contract.sh` 后再广泛读取；长任务跨会话前必须更新 checkpoint 和 handoff，下一会话先读记录再继续。

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

## 轻量文档整理

材料和目标已确定时，测试用例、检查清单和变更说明默认走 L1 / plan 的轻量文档分支，不新增阶段。例如：

```text
/yxj-work 结合 plans/0.0.15/ 和提交 9db0dcf 整理手工测试用例，我要测试下
/yxj-work 根据这三个已合并提交整理更新说明，不执行测试
```

流程：按 `skills/yxj-work/templates/document-task.md` 填最小契约与状态 → 校验 → 读固定主材料 → 写初稿 → 只为具体缺口补读 → 核对覆盖与可理解性 → 交付。默认不搭建环境、不代跑测试、不做全量代码审查或发布检查；「我要测试下」是用户拿用例去测，不是授权代跑。未确定功能仍走 design，实施计划保留原 plan 分支，实际执行进入 exec。

主材料原则上在 **6 次资料工具调用**检查点前形成初稿或写明具体缺口；到 **20 次总工具调用**必须判断是否交付或阻塞。按实际动作计数，批量读取不能绕过。仅可选细节缺失可说明后交付；必过项不能降级，部分初稿不能标 done。单纯读取或查询环境不算文档进展。当前工作区合并只作为执行前提，文档依据固定提交；若纳入未提交差异，先明确范围。

模板保留现有 Acceptance、证据绑定和指纹格式，默认调用校验器而非研究其源码。检查点是技能约束，**不是宿主自动拦截或速度保证**；规则字符串检查不能证明模型一定遵守。文档完成验证覆盖与可理解性，不证明网站行为已跑通，交付注明「用例已整理，测试未执行」。

## 契约、状态和证据

新任务的 `contract.md` 保留 `done_when` 摘要，并增加带编号的 `Acceptance` 验收条件。每条条件必须写 `outcome`、`verification`、`verification_type`、`layer` 和 `required`。同时写 `risk`、`risk_reason`、`review_policy`、`contract_revision`、`Decision Gates` 和 `Contract Changes`。

任务规模 `L1/L2/L3/long` 与影响风险 `low/medium/high` 分开：低风险可自动进入执行；中风险默认需要确认和只读审查；高风险需要确认和完整审查。不可逆操作、花钱、对外发布、生产变更和需求范围变化不能自动豁免。

执行前运行：

```bash
bash skills/yxj-work/scripts/check-contract.sh .work-docs/tasks/<task-id>
```

`check-contract.sh` 只检查契约结构、枚举、验收条件和风险策略关系，不判断自然语言质量。字段必须从第 1 列写成 `key: value`，写成 Markdown 列表项 `- key: value` 会被直接拦下（提示 `fields must use key: value at column 1`）。默认模式为 `--ready`；中/高风险契约的确认门未完成时只允许 `--draft`；`--seal` 把契约快照固化到 `audit/contract-r<N>.md`，`--locked` 用于交付前复核历史快照与变更记录齐全。历史契约没有 `Acceptance` 时保持兼容，不强制迁移。

`state.md` 是按行记录的状态文件：除了基本字段，还要记录 `calls_since_progress`、`last_progress_at`、`budget: used/limit`、`strategy_fingerprints`。新格式任务的 `contract_revision` 和 `contract_fingerprint` 必须与契约一致，启用新版完成门时增加 `evidence_schema: 2`；`required_verification` 必须引用 `A1` 等验收条件编号；标记 done 时必须覆盖并通过所有 `required: yes` 条件。每条 evidence 都记录 `acceptance`、`command`、`run_at`、`result` 和相关文件的 `last_edit_at`，且对应证据文件必须存在；运行时间早于文件修改时间的证据不能支撑交付。历史已完成的 v2 state 不带 `evidence_schema: 2` 时保持兼容读取。

`check-state.sh`（随技能安装到 `skills/yxj-work/scripts/`）可验证状态文件，写 `status: done` 前必须运行并通过；新契约的每条 required 验收必须绑定完整 evidence（包含 `acceptance`、`command`、`run_at`、`result`、`last_edit_at`），中/高风险完成还必须有匹配 `review_policy` 的 `review_evidence`。`tests/fixtures/`、`test-fixtures.sh` 和 `test-v2-lifecycle.sh` 覆盖合法完成、未运行、过期证据、无进展超阈值、阻塞字段缺失、新契约关联和完成门失败场景。关键词或 grep 检查只属于 `static`（静态）证据，不能单独证明行为生效。

轻量文档的边界和初稿检查点见上一节；其他正式阶段采用三条效率规则：按断言驱动读取（先列断言，再定位实现符号和局部代码）；模型请求首次超时后先写 `audit/` 恢复摘要，不原样重试，并在宿主允许时降低思考级别或切换更快模型；低风险、只读、`review_policy: auto` 的审查使用轻量 review，只保留验收所需的 contract、evidence、state 和校验脚本。

## 完成判定

任务只有在以下条件同时满足时才能写 `status: done`：

- 所有 required 验证项为 `passed`；
- 所有 required 子任务已结束；
- 没有未处理的越界文件；
- 所有决策门允许交付；
- 每个结论都有 evidence 指针。

`failed`、`blocked`、`not_run`、未解决决策门、in_progress required 子任务或缺少 evidence 时禁止标记 `done`。optional 项必须在契约中声明并写明跳过原因。启用 `evidence_schema: 2` 的新任务还有两道完成门：每条 required 验收都必须绑定一条完整 evidence（含 `acceptance`、`command`、`run_at`、`result`、`last_edit_at`，且证据文件真实存在）；中/高风险任务还必须有一条与契约 `review_policy` 匹配的 `review_evidence`（审查文件存在且 `status=passed`）。

## 熔断

每个子任务独立计数。任一条件触发即停止当前子任务：连续 3 次 required 验证失败、60 次工具调用无进展、30 分钟无有效进展、第三方 skill 越界写入，或共同前提被证据否定。

熔断必须：停止同策略重试；在 `audit/` 记录策略、错误和证据；写 `status: blocked`、`blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；写 checkpoint/handoff；禁止父任务标记 done。L1/L2/L3 的预算分别为 60/150/400 次工具调用，L3 另有 8 小时上限；无进展熔断阈值为 L1/L2 20 次、L3/long 每子任务 60 次或 30 分钟。开工后发现真实范围将超出当前 level 预算时，在 contract 与 state 显式升级 level 并记录原因，不允许静默超支。预算耗尽写 checkpoint，不标记 done，交用户决定是否追加预算。

恢复必须先读状态、最近 checkpoint、失败策略和 evidence，验证阻塞条件已解除或采用有证据的新策略；不得重复相同失败策略。固定收尾顺序为：写 contract → 写 evidence → 写报告 → 写 state → `check-contract.sh` → `check-state.sh` → 更新 `.work-docs/index.md`。契约最后一次修改后才计算 fingerprint；校验失败必须换策略修复，不能原样重跑。

## 更新与卸载

更新前从源仓库运行 `check-repo.sh`，再用 `install.sh --update`。卸载只删除本仓库安装、且仍带有 `.yxj-work-installed` 标记的目录（`scripts/runtime-skills.txt` 列出的全部目录）；不要删除任务目录或用户文件。

## 验收

```bash
bash scripts/check-repo.sh
bash scripts/test-contract.sh
bash scripts/test-fixtures.sh
bash scripts/test-v2-lifecycle.sh
bash scripts/test-flow.sh
bash scripts/test-document-template.sh
bash scripts/test-install.sh
tmp="$(mktemp -d)"
bash scripts/install.sh --dest "$tmp"
bash scripts/check-workflow.sh --source "$PWD" --installed "$tmp"
```

详细边界见 `docs/architecture.md` 和 `docs/file-boundary.md`。

真实会话中观察到的行为场景与处置状态（含会话 ID 与证据）记在 `docs/session-scenarios.md`，后续新场景直接追加到该文件。
