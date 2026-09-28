---
name: yxj-work
description: 独立开发、调研、计划、执行、修复和审查入口；正式任务将工作流文件收敛到当前执行目录的 .work-docs。
disable-model-invocation: true
---

# yxj-work

每次调用都是一个新任务。命令后的文字是任务说明。源仓库是唯一事实源；本 skill 不读取或修改其他同名/旧 skill。

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

按目标和允许改动范围路由，不按关键词机械触发。预计一个简单事实回答即可完成的请求走 L0；需要真实读取、持久证据、修改或多阶段推进时至少走 L1。

## 工作根和任务目录

L1/L2/L3 任务以命令实际执行目录为工作根，创建或复用唯一 `.work-docs/`。发现它不是目录、不可写或归属不明时停止，不覆盖。

```text
.work-docs/
├── README.md
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

工作流生成的持久文件只能放上述目录。项目代码是用户任务目标，可按契约修改，但不把项目代码伪装为工作流产物。

## 契约和状态

- L1：一句 `done_when`、允许范围、验证方式和 unknowns。
- L2：任务类型、done_when、允许/禁止改动、验证层级、产物位置、阶段和下一入口。
- L3：L2 加每个 checkpoint 的状态、证据、依赖、阻塞和第一步。

`state.md` 使用简单的按行格式：每个字段一行 `key: value`；required 验证一行 `required_verification: name status=passed evidence=path`；证据一行 `evidence:name|command=...|run_at=...|result=...|last_edit_at=...`。固定记录 `task_id`、`level`、`stage`、`status`、`done_when`、`evidence`、`unknowns`、`blocked_by`、`unblock_condition`、`next_action`、`calls_since_progress`、`last_progress_at`、`budget`（`used/limit`）、`strategy_fingerprints`、`updated_at`。验证层级为 `syntax/config`、`static`、`runtime/local`、`external`、`consumer`，每层只能是 `passed|failed|not_run|blocked` 并带 evidence 指针。

只有全部 required 验证为 `passed`、required 子任务已结束、没有越界文件、决策门允许交付且每个结论有 evidence，才能写 `status: done`。`failed`、`blocked`、`not_run`、active required 子任务、未解决决策门或无 evidence 时禁止 done。optional 项必须在契约中声明并写明跳过原因。

## 进展、预算和熔断

有效进展只有两种：某个 `done_when` 条目拿到新 evidence，或某个 required 验证从 `failed|not_run` 变为 `passed`。每次有效进展都更新 `state.md` 的 `calls_since_progress`（归零）、`last_progress_at`、`budget`（`used/limit`）和 `strategy_fingerprints`。`evidence freshness`（证据新鲜度）按 `run_at` 不早于相关文件 `last_edit_at` 判断；交付时关键词或 grep 检查只标为 `static`。安装标记使用独立的 `source=` 行。

每个子任务单独计数。L1/L2 在 20 次工具调用无进展时熔断；L3 和 long 模式每个子任务在 60 次工具调用或 30 分钟无进展时熔断。无论层级，同一命令与同一错误首行出现 2 次就熔断；错误不同但 required 验证连续失败 3 次也熔断；同一类工具或命令报错 2 次必须换方法，不能原样重试；错误各不相同时，required 验证连续 3 次失败也必须熔断。L1/L2/L3 的预算分别为 30/100/400 次工具调用（L1 为 30 次工具调用）；L3 另有 8 小时上限。任务说明另行指定时，以任务说明为准。

策略指纹固定为 `修改文件 + 执行命令 + 错误首行`，记录在 `audit/`。恢复时，新指纹不能与已有指纹相同；说不出新旧策略差异就停下交给用户。

熔断时停止修改和同策略重试，在 `audit/` 记录错误摘要、失败动作、策略指纹和 evidence；写 `status: blocked`、`blocked_by`、`attempted_paths`、`shared_assumption`、`unblock_condition`、`next_action`；写 checkpoint/handoff。父任务不得 done，只有不依赖阻塞项的独立子任务可继续。恢复前先读状态、checkpoint、失败策略和 evidence，重新验证前提或采用有证据的新策略，不能重复同一失败策略。

## 第三方 skill

第三方 skill 不会自动继承本规则。调用前分类为只读、可指定输出根、固定/未知写入。可指定输出根时传入 `.work-docs/tasks/<task-id>/outputs|evidence|tmp`；固定/未知写入只能隔离验证，否则 `blocked`。调用前后保存目录清单。发现越界文件时停止，记录：

```text
blocked_by: external_skill_write_outside_work_docs
```

未经授权不移动、删除或覆盖越界文件。

## 交付

交付必须包含真实验证输出、证据位置、未验证项、阻塞项和需要用户判断的点。退出码、文件存在、编译通过或 agent 自报完成不能单独满足完成条件。
