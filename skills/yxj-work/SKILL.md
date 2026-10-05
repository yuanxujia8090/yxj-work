---
name: yxj-work
description: 独立开发、调研、计划、执行、修复和审查入口；正式任务将工作流文件收敛到当前执行目录的 .work-docs。
disable-model-invocation: true
---

# yxj-work

每次调用都是一个新任务。命令后的文字是任务说明。源仓库是唯一事实源；本 skill 不读取或修改其他同名/旧 skill。

## 技能调用边界

`skills/` 下的技能都设了 `disable-model-invocation`，不会因任务内容被模型自动唤起；不得自动扫描、推荐、注入用户提示词或替用户触发任何技能。流程自带的参考技能由本入口按阶段主动读取（见“参考技能”），用户也可主动点名调用。无论哪种方式，加载后仍须遵守当前任务的 contract、`.work-docs` 文件边界、熔断规则和验证要求。

## 路由

- `fast-answer` / L0：快问快答、术语解释、简单命令说明、单一事实确认。直接回答，不创建 `.work-docs`、contract、state、handoff 或交付文件。
- `investigate`：现状、定位、恢复。
- `research`：外部事实、产品、市场、用户或技术选型研究。
- `design`：方案设计，不改代码。
- `plan`：逐任务实施规格。
- `exec`：按计划修改并验证。
- `bugfix`：复现、根因、最小修复、回归。
- `review`：只读审查。
- `ops`：平台操作手册；不代点网页。
- `mixed`：研究 → decision gate → design/plan → exec → verify。

按目标和允许改动范围路由，不按关键词机械触发。技能唤起不属于本路由的一部分：技能只在用户主动点名，或本入口按“参考技能”表主动读取时加载。预计一个简单事实回答即可完成的请求走 L0；需要真实读取、持久证据、修改或多阶段推进时至少走 L1。

常见任务链先按下面的完整路径判断，再进入单个阶段：

- 开发：`design → plan → exec → review`。需求明确且改动很小，可跳过 `design`，但要在 contract 记录原因。
- 问题排查与修复：`investigate → bugfix → review`。无法稳定复现时停在 `investigate`，不要假装进入修复。
- 调研：`research → decision gate`；只有 `proceed` 才进入 `design/plan → exec → review`，`design_only`、`gather_more`、`do_not_build` 在当前任务收口。

每进入一个阶段，先读对应 playbook，再读表中的参考技能，最后按 playbook 写产物和验证证据。阶段与文件的唯一映射如下：

| 阶段 | playbook | 主动读取 |
|---|---|---|
| investigate | `playbooks/investigate.md` | `../yxj-how/SKILL.md`、`../yxj-blast-radius/SKILL.md` |
| research | `playbooks/research.md` | `../yxj-why/SKILL.md`、`../yxj-how/SKILL.md` |
| design | `playbooks/design.md` | `../yxj-codebase-design/SKILL.md`、`../yxj-architect/SKILL.md`、`../yxj-arena/SKILL.md`、`../yxj-principle-redesign-from-first-principles/SKILL.md`、`../yxj-principle-foundational-thinking/SKILL.md`、`../yxj-principle-outcome-oriented-execution/SKILL.md`、`../yxj-prototype/SKILL.md` |
| plan | `playbooks/plan.md` | `../yxj-principle-build-the-lever/SKILL.md` |
| exec | `playbooks/exec.md` | `../yxj-typescript-best-practices/SKILL.md`、`../yxj-principle-type-system-discipline/SKILL.md`、`../yxj-principle-boundary-discipline/SKILL.md`、`../yxj-principle-laziness-protocol/SKILL.md` |
| bugfix | `playbooks/bugfix.md` | `../yxj-principle-fix-root-causes/SKILL.md`、`../yxj-principle-attack-the-premise/SKILL.md` |
| review | `playbooks/review.md` | `../yxj-requesting-code-review/SKILL.md`、`../yxj-receiving-code-review/SKILL.md`、`../yxj-interrogate/SKILL.md`、`../yxj-principle-prove-it-works/SKILL.md` |
| ops | `playbooks/ops.md` | `../yxj-wizard/SKILL.md`、`../yxj-create-verification-skill/SKILL.md` |
| mixed | `playbooks/mixed.md` | 按实际阶段读取上表，不新增一套技能清单 |
| fast-answer | 不读 playbook | 不读取任何技能 |
| 按需 | 无固定 playbook | `../yxj-unslop/SKILL.md`、`../yxj-principle-guard-the-context-window/SKILL.md`、`../yxj-principle-encode-lessons-in-structure/SKILL.md`、`../yxj-principle-separate-before-serializing-shared-state/SKILL.md`、`../yxj-resolving-merge-conflicts/SKILL.md`、`../yxj-technical-writing/SKILL.md`、`../yxj-teach/SKILL.md` |

第三方技能按 `playbooks/third-party-skill.md` 处理，不因它被列在仓库里就自动调用。同一技能在多行出现时只读一次。读取后若其规则与当前契约冲突，以契约为准并在 `audit/` 记录差异。

## 阶段执行表

上表同时是阶段、playbook 和参考技能的唯一映射；不要再为同一阶段建立第二份清单。

## 工作根和任务目录

L1/L2/L3 任务以命令实际执行目录为工作根，创建或复用唯一 `.work-docs/`。发现它不是目录、不可写或归属不明时停止，不覆盖。

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

`<task-id>` 是目录名，形如 `{YYYYMMDD}-{NN}-{slug}`（例：`20260928-01-yxj-work-independent-workflow`）。`{YYYYMMDD}` 为任务创建当天的本地日期，`{NN}` 为**当日**两位自增序号（从 `01` 起，不回收空号），`{slug}` 为小写 kebab-case 任务短名。取号前先读 `.work-docs/index.md`：范围相同且仍在进行时续用原 id；否则扫 `tasks/` 下同日期目录取最大序号 +1 并追加索引行。契约与状态里的 `task_id` 等于完整目录名。并发场景（多个会话同时工作）下，追加索引行后复查一次 `tasks/` 与索引：若同日同号已被占用，保留先创建者，后来者顺延到下一个可用序号，并在 `audit/` 记录该冲突。

工作流生成的持久文件只能放上述目录。项目代码是用户任务目标，可按契约修改，但不把项目代码伪装为工作流产物。

由其他入口技能或外部会话产生的 `.work-docs` 任务属于半合规：本入口可以读取和续接；首个续接的会话须补齐 contract/state 骨架，并在 `audit/` 记录。

## 契约和状态

新任务的 `contract.md` 在保留 `done_when` 摘要的同时，增加 `Acceptance`（验收条件）章节。每条验收条件使用唯一编号（如 `A1`），并写明 `outcome`（可观察结果）、`verification`（验证方式）、`verification_type`（验证类别）、`layer`（验证层级）和 `required`（是否必过）。`verification_type` 允许 `automatic|manual|consumer|external`；脚本只校验结构，不给自然语言打分。

新任务还必须写 `risk: low|medium|high`、`risk_reason`、`review_policy: auto|user-confirm|full-review`、`contract_revision`、`Decision Gates` 和 `Contract Changes`。任务规模 `L1/L2/L3/long` 与影响风险分开判断：低风险可自动进入执行；中风险默认需要用户确认和只读审查；高风险必须用户确认和完整审查。涉及不可逆操作、花钱、对外发布、生产或需求范围变化时，决策门不能被自动豁免。

开始执行前运行 `skills/yxj-work/scripts/check-contract.sh <task-dir>`。它检查字段、枚举、验收条件、风险策略和版本结构；不判断文字是否“足够聪明”。`check-state.sh` 继续检查状态和证据，并对新格式任务检查 `contract_revision`、`contract_fingerprint` 与 `required_verification` 的验收编号引用。历史契约没有 `Acceptance` 时保持 v1.x 兼容，不强制迁移。

契约实质变化必须提升 `contract_revision`，在 `Contract Changes` 中记录旧值、新值、原因、批准人和受影响证据；删除、放宽或降低 required 验收条件必须重新经过对应决策门。

- L1：一句 `done_when`、允许范围、验证方式和 unknowns。
- L2：任务类型、done_when、允许/禁止改动、验证层级、产物位置、阶段和下一入口。
- L3：L2 加每个 checkpoint 的状态、证据、依赖、阻塞和第一步。

`state.md` 使用简单的按行格式：每个字段一行 `key: value`；新格式任务还记录 `contract_fingerprint`（契约指纹，即契约文件内容摘要）；required 验证一行 `required_verification: name status=passed evidence=path`；证据一行 `evidence:name|command=...|run_at=...|result=...|last_edit_at=...`。固定记录 `task_id`、`level`、`stage`、`status`、`done_when`、`evidence`、`unknowns`、`blocked_by`、`unblock_condition`、`next_action`、`calls_since_progress`、`last_progress_at`、`budget`（`used/limit`）、`strategy_fingerprints`、`updated_at`。验证层级为 `syntax/config`、`static`、`runtime/local`、`external`、`consumer`，每层只能是 `passed|failed|not_run|blocked` 并带 evidence 指针。`status` 仅取 `in_progress|done|blocked|stopped|cancelled`；`stage` 使用路由中定义的阶段名，交接收尾时记 `handoff`。这两个枚举由 `scripts/check-repo.sh` 与 `check-state.sh` 双向断言，改一处不同步会直接报错。

只有全部 required 验证为 `passed`、required 子任务已结束、没有越界文件、决策门允许交付且每个结论有 evidence，才能写 `status: done`。`failed`、`blocked`、`not_run`、in_progress required 子任务、未解决决策门或无 evidence 时禁止 done。optional 项必须在契约中声明并写明跳过原因。

## 进展、预算和熔断

有效进展只有两种：某个 `done_when` 条目拿到新 evidence，或某个 required 验证从 `failed|not_run` 变为 `passed`。每次有效进展都更新 `state.md` 的 `calls_since_progress`（归零）、`last_progress_at`、`budget`（`used/limit`）和 `strategy_fingerprints`。`evidence freshness`（证据新鲜度）按 `run_at` 不早于相关文件 `last_edit_at` 判断；交付时关键词或 grep 检查只标为 `static`。

每个子任务单独计数。L1/L2 在 20 次工具调用无进展时熔断；L3 和 long 模式每个子任务在 60 次工具调用或 30 分钟无进展时熔断。无论层级，同一命令与同一错误首行出现 2 次就熔断；错误不同但 required 验证连续失败 3 次也熔断；同一类工具或命令报错 2 次必须换方法，不能原样重试。L1/L2/L3 的预算分别为 60/150/400 次工具调用；L3 另有 8 小时上限。开工后发现真实范围将超出当前 level 预算（例如复现或实测成本显著高于预估）时，在 contract 与 state 显式升级 level 并记录原因，预算上限同步调整；不允许静默超支。预算耗尽时按熔断处理：写 checkpoint 并保持非 done，交用户决定是否追加预算。任务说明另行指定时，以任务说明为准。

策略指纹固定为 `修改文件 + 执行命令 + 错误首行`，记录在 `audit/`。恢复时，新指纹不能与已有指纹相同；说不出新旧策略差异就停下交给用户。

熔断时停止修改和同策略重试，在 `audit/` 记录错误摘要、失败动作、策略指纹和 evidence；写 `status: blocked`、`blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；写 checkpoint/handoff。父任务不得 done，只有不依赖阻塞项的独立子任务可继续。恢复前先读状态、checkpoint、失败策略和 evidence，重新验证前提或采用有证据的新策略，不能重复同一失败策略。

## 派发失败降级

子 agent 或 category 派发因模型或配置不可用而失败时：把失败写入 `audit/`（策略指纹）→ 换等价 agent 类型重试一次 → 仍失败则由主会话接替执行。降级不改变 required 验证、文件边界与调用计数。

## 第三方 skill

第三方 skill 不会自动继承本规则。调用前先读 `playbooks/third-party-skill.md`，再分类为只读、可指定输出根、固定/未知写入。可指定输出根时传入 `.work-docs/tasks/<task-id>/outputs|evidence|tmp`；固定/未知写入只能隔离验证，否则 `blocked`。调用前后保存目录清单。发现越界文件时停止，记录：

```text
blocked_by: external_skill_write_outside_work_docs
```

未经授权不移动、删除或覆盖越界文件。

## 交付

交付必须包含真实验证输出、证据位置、未验证项、阻塞项和需要用户判断的点。退出码、文件存在、编译通过或 agent 自报完成不能单独满足完成条件。

写 `status: done` 前，用本技能目录下的校验脚本自查：`bash <本技能目录>/scripts/check-state.sh .work-docs/tasks/<task-id>`；输出 `passed` 才允许 done；校验失败则修正 state 或保持非 done。
