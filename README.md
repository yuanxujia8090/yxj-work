# x-rail

独立的工作流技能仓库。源仓库是唯一事实源。安装形态为副本或直达源仓库的软链。

[使用指南](docs/usage-guide.html)介绍阶段和常见场景。[0.0.3 方案](plans/0.0.3/README.md)规定本地实现与真实行为验证的边界。

## 入口与加载

- `/x-rail`：普通任务，支持快速回答、调查、研究、设计、计划、执行、修复、审查、操作指引和组合任务。
- `/x-rail-long`：跨会话、外部等待或独立依赖汇总。多个阶段本身不触发长模式。
- `/x-handoff`：用户明确调用时写当前任务交接。
- `/x-self-check`：用户明确调用时只读分析七日或三周记录。

`scripts/runtime-skills.txt` 是安装范围的唯一来源。当前为 4 个入口和 32 个辅助技能。所有技能设 `disable-model-invocation: true`，不会由任务内容自动唤起。主入口 XML 的 routing 模块维护阶段、说明文件和按需参考映射。TypeScript 规则仅在项目规范不足且当前代码使用该语言时读取。设计不默认读取全部参考技能，也不默认委派。

XML（Extensible Markup Language，可扩展标记语言）像组件标签，只分隔不同职责。它不授予权限。用户只要分析时只在回复交付，不创建任务或目标文件。用户要写文档时只写授权目录。

## 安装

需要 Bash 和 Python 3.10 或更新版本。只使用标准库，不新增第三方包。`zoneinfo` 使用系统时区数据。

```bash
bash scripts/check-repo.sh
bash scripts/install.sh --dest <新的隔离目录>
bash scripts/check-workflow.sh --source "$PWD" --installed <隔离目录>
```

复制安装拒绝覆盖。`--update` 会删除并替换已标记目录，需要事先确认风险。软链安装用 `--link`，正确已有链接保持不变；外来链接、断链、目录均拒绝接管。`--unlink` 删除指向本仓库的链接，需要明确清理授权。不要因安装测试就修改 `~/.pi/agent/skills`。

真实全局安装前先检查路径和归属。软链指向主仓库时，隔离分支的改动不会自动生效。

## 任务记录

正式任务在命令实际执行目录下创建 `.work-docs/tasks/<task-id>/`。同范围进行中任务续用编号。编号为 `{YYYYMMDD}-{NN}-{slug}`，日期为创建日，序号当日自增且不回收。工作流记录只写该目录；项目代码和用户授权的项目文档是目标文件，不伪装为记录。

```text
.work-docs/
├── index.md
└── tasks/<task-id>/
    ├── contract.md
    ├── state.md
    ├── handoff.md
    ├── evidence/
    ├── outputs/
    ├── audit/
    └── tmp/
```

契约记录目标、范围、禁止动作、风险、审查策略、版本、Acceptance（编号验收条件）、Decision Gates（授权记录）和变更。每条验收有 outcome、verification、verification_type、layer、required。可选项必须预先写 skip_reason。字段从第一列写 `key: value`，不是 Markdown 列表。

风险决定审查强度。确认只针对不可逆、支出、对外发布、需求范围变化。`action_categories: none` 可以豁免确认，不豁免所需审查；有敏感动作时必须绑定当前动作的用户确认来源。独立审查需要委派授权；未获授权单列阻塞，不能把主会话核对冒充独立审查。

## 严格检查与完成

从源或安装技能目录调用，不要求消费者项目含 `skills/`：

```bash
python3 <skill-dir>/scripts/task.py seal <task-dir>
python3 <skill-dir>/scripts/task.py check <task-dir>
python3 <skill-dir>/scripts/task.py complete <task-dir> --candidate <task-dir>/candidate.md
```

顺序为写契约、封存、实施与取证、准备候选状态、检查并提交、更新索引。候选必须 `status: done`。失败保留正式状态、索引和候选。完成前再次核对契约、状态、候选字节和证据输入。单任务保持一个写入者。此机制防误操作，不抵御同等写权限的恶意执行者。

两个 shell 检查入口默认严格模式：

```text
bash skills/x-rail/scripts/check-contract.sh TASK_DIR [--draft|--ready|--seal|--locked] [--strict|--legacy-readonly]
bash skills/x-rail/scripts/check-state.sh TASK_DIR [--strict|--legacy-readonly]
```

退出码 0 为当前模式通过，1 为材料或验收失败，2 为参数或运行依赖错误。历史必须显式 `--legacy-readonly`，只读，不允许据此提交新完成，也不能封存。漏字段不会自动降级。不批量迁移历史任务，不补造过去快照。

新状态必须 `evidence_schema: 2`，绑定 contract_revision 和 contract_fingerprint。每条 passed 必需验收绑定唯一非空证据。`not_run` 可以没有证据文件，不能制造空白通过记录。

```text
required_verification: A1 status=passed evidence=evidence/check.txt
evidence:check|acceptance=A1|command=实际命令或人工核对|run_at=2026-10-10T02:00:00Z|result=passed|last_edit_at=2026-10-10T01:59:00Z|inputs=evidence/check.inputs.json|contract_revision=1
```

输入摘要记录版本、契约版本、绝对 workspace_root、相关文件相对路径、存在状态和原字节 SHA-256（内容摘要）。只绑定该项相关材料，允许无关文件变化。已删除文件记录 absent；状态、证据和快照不自我绑定。路径不能越界。命令文本是数据，校验器不执行。时间带时区，转换 UTC（Coordinated Universal Time，协调世界时）后比较。审查报告同样绑定输入、契约版本和时间，不能以旧报告为改后的代码放行。

`status` 为 `in_progress|done|blocked|stopped|cancelled`。完成要求全部必需验收、必需依赖、授权、快照、输入与预算通过。子任务 done 不自动通过父验收。证据只证明实际观察到的对象，静态文本不能证明模型会遵守。

## 取证与轻量文档

[document-task.md](skills/x-rail/templates/document-task.md)提供已有材料的文档模板。默认不搭环境、不代跑、不全量审查、不追踪别的会话。先覆盖清单和初稿，再只补具体缺口。6 次资料动作、20 次总动作是交付检查点，不是宿主自动拦截。合并命令仍按实际动作计数。最终注明“用例已整理，测试未执行”。

大输出先工具内统计、筛选或索引。主会话默认直接执行。委派需当前用户或项目规则明确授权，使用 [child-task.md](skills/x-rail/templates/child-task.md)，先发现能力，正式绑定输出，回收原运行和实际产物。基础设施失败暂停原依赖，不换协议、不自动重发、不冒充独立审查。

## 预算与恢复

L1/L2/L3 默认 60/150/400 次工具调用。无进展提醒为 20/60 次；长任务另有 30 分钟无进展和 8 小时总上限。used 小于 limit 可继续；相等须收口，合法完成候选可提交；超限只能保存有原因的 blocked、stopped 或 cancelled。离线脚本证明记录一致，不宣称宿主强制限额。暂停和等待用户分开记录。

恢复读取索引、contract、state、最近 checkpoint、handoff、audit/runs.json、相关 evidence；核对工作区、版本、未提交差异和输入。原外部运行先查再恢复，不可查时 unknown 或 blocked，不重复启动。[long-task.md](skills/x-rail/templates/long-task.md)给依赖和运行引用格式。

## 自检与验证

```bash
python3 skills/x-self-check/scripts/analyze_sessions.py --sessions-root <日志目录> --days 7 --timezone Asia/Shanghai --format json
python3 scripts/test-task-checks.py
python3 scripts/test-skill-xml.py
python3 scripts/test-self-check.py
python3 scripts/test-html-check.py
bash scripts/test-worktree.sh
bash scripts/test-contract.sh --keep-artifacts
bash scripts/test-fixtures.sh
bash scripts/test-v2-lifecycle.sh
bash scripts/test-flow.sh
bash scripts/test-skill-metadata.sh --keep-artifacts
bash scripts/test-document-template.sh
bash scripts/test-install.sh --keep-artifacts
```

`--days 21` 支持三周；指定窗口用成对带时区的 `--start/--end`，结束不包含。脚本只输出，不联网、不执行日志命令。默认摘要不输出提示、命令正文、邮箱或密钥。历史版本缺失写 null，不用当前文件代替。

核对任务记录时成对给 `--task-root <任务目录集合>` 和 `--task-mode strict|legacy-readonly`，目录可重复。只核对明确关联编号，输出检查器内容摘要和记录字节一致性；历史格式失败不表示交付失败。没有显式模式不读取任务记录。

测试使用全新目录并保留产物。`--test-root DIR` 指定目录必须是新目录。删除型安装回归等待具体授权。结构、确定性行为、真实模型演练分别验收；没有模型演练证据不能称全部版本完成或稳定提速。

详细说明见 [架构](docs/architecture.md)、[文件边界](docs/file-boundary.md)、[审查委派](docs/review-delegation.md)和[会话场景](docs/session-scenarios.md)。
