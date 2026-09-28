# skills 目录说明与外部 skill 筛选清单

本目录是 yxj-work 源仓库的 skill 源目录。除自研的 `yxj-work` / `yxj-work-long` / `yxj-work-handoff` 外，
2026-09-28 从三个外部 skill 库筛出 **27 个** skill，按 `yxj-<原名>` 命名复制进来，作为**素材库**，等待整合。
另有 **11 个**因与全局已装 skill 重复，没有保留在本仓库（2026-09-28 用户删除暂存目录）。
**Pi 全局技能目录（`~/.pi/agent/skills/`、`~/.agents/skills/`）不由本仓库操作**：本仓库只提供 `scripts/install.sh`
供用户自行安装，不读写全局目录。

来源：`pstack` = `~/Downloads/plugins-main/pstack/skills`；`superpowers` = `~/Downloads/superpowers-main/skills`；
`mattpocock` = `~/Downloads/mattpocok-skills-main/skills/engineering`。三个源库合计 80 个 skill。

## 0. 先读：这 27 个 skill 目前不会被加载

事实（已核对 Pi bundle 源码与仓库脚本）：

- Pi 加载 skill 的两个位置是 `~/.pi/agent/skills/`（全局，`agentDir`）和 `<cwd>/.pi/skills/`（项目级，需项目被 trust）。
  本仓库的 `skills/` **不是**这两个路径之一。
- `scripts/install.sh` 的安装白名单是硬编码的三个：`yxj-work`、`yxj-work-long`、`yxj-work-handoff`。
  新复制的 skill 不在白名单里，装了也不会生效。
- `bash scripts/check-repo.sh` 通过 —— 新增目录不会破坏现有门禁。

生效路径，整合时选一条：

| 路径 | 做法 | 生效范围 |
|---|---|---|
| A（推荐） | 把入选的 skill 加进 `install.sh` 白名单，随仓库装进 `~/.pi/agent/skills/` | 全局，所有项目 |
| B | 在需要的项目里建 `<项目>/.pi/skills/`，软链或复制本目录的 skill | 仅该项目，且需项目 trust |
| C | 保持在 `skills/` 只作素材库，由 `yxj-work` 的 playbook 按需引用其正文 | 不自动触发 |

路径 A/B 生效后要与**全局已装**的同名 skill 划清主次，否则同一需求触发两套。

## 1. 保留的 27 个 skill

复制规则：整目录 `cp -R`（`references/`、`scripts/`、`agents/` 一并带入）；`SKILL.md` 的 frontmatter
`name:` 同步改为 `yxj-<原名>`。每个目录的文件数与源目录逐一对齐。

### 1.1 调研与理解（对应 playbook：investigate / research）

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-why` | pstack | 追问"为什么这样设计"：设计缘由、回归、复盘，带证据账本 | `references/sources/` 里的 slack/notion/sentry/linear 等连接器在你环境多不可用，需裁剪 |
| `yxj-how` | pstack | 代码走查、归属与分层问题（"该放哪"） | 依赖缺失的 `pstack-models.md`（已就地标注） |
| `yxj-teach` | pstack | 把一坨工作讲清楚给人听懂（调用 `how` + `why` + `unslop`） | 内部按旧名引用这三个 skill，整合时需改名 |
| `yxj-blast-radius` | pstack | 改动的影响面 + 用**运行真实代码**证明那条安全前提 | 引用 `how` / `why` / `unslop` / `arena` |

### 1.2 设计（对应 playbook：design）

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-architect` | pstack | 先定类型、签名、模块结构，再进入实现 | 依赖 `arena`（已补入）与 `how` / `why` / `interrogate` |
| `yxj-arena` | pstack | 并行跑 N 个候选方案，选一个做底、把落选者的强处嫁接进来 | 依赖缺失的 `pstack-models.md`（已就地标注） |
| `yxj-codebase-design` | mattpocock | 深模块设计的共享词汇（接口 vs 实现深度） | 产出物 `CONTEXT.md` 属项目文档（已就地标注） |
| `yxj-prototype` | mattpocock | 造一个丢弃型原型回答设计问题（状态模型/交互是否成立） | 产物落 `.work-docs/.../tmp/`（已改写） |

### 1.3 计划与执行（对应 playbook：plan / exec）

原计划纳入的 superpowers 执行类 skill（`writing-plans`、`subagent-driven-development`、
`dispatching-parallel-agents`、`test-driven-development`）因为全局已有同源实体，**未纳入本仓库**。执行阶段的能力暂由自研 `exec` playbook 承担；
需要时从顶部列出的源库路径重新复制。

### 1.4 修复（对应 playbook：bugfix）

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-principle-fix-root-causes` | pstack | 每个症状追到根因，拒绝用空值守卫掩盖崩溃 | 能力与未保留的 `systematic-debugging` 互补，不要两者同时启用 |
| `yxj-principle-attack-the-premise` | pstack | 多个修复共享同一前提且反复失败时，先普查前提本身 | 引用 4 条其它原则（已补入） |

### 1.5 审查（对应 playbook：review）

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-interrogate` | pstack | 多模型对抗式审查，专找盲点 | 依赖缺失的模型清单；`Task tool` / `subagent_type` 是 Cursor 命名 |
| `yxj-requesting-code-review` | superpowers | 请求审查时该给什么（含子 agent 评审人 prompt） | 全局同名项是**断链**，所以这份是唯一可用副本 |
| `yxj-receiving-code-review` | superpowers | 收到审查意见后如何处置（含意见不清/技术上可疑时） | 同上 |
| `yxj-create-verification-skill` | pstack | 生成"像用户一样驱动应用"的项目级验证 skill | 产物落 `.pi/skills/verify-<app>/`（已改写）；引用示例 `artifacts/*.aria.txt` 是模板非依赖 |
| `yxj-principle-prove-it-works` | pstack | 声明完成前，对着真实产物验证而不是代理指标 | 与自研 done gate 同一纪律，注意不要保留两套阈值 |
| `yxj-principle-guard-the-context-window` | pstack | 上下文吃紧时把批量活路由给子 agent，主线程只留摘要 | 与自研 `calls_since_progress` 预算互补 |

### 1.6 交付与收尾

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-resolving-merge-conflicts` | mattpocock | 解 merge/rebase 冲突的流程 | 无外部依赖 |

### 1.7 横向能力

| skill | 来源 | 干什么 | 注意 |
|---|---|---|---|
| `yxj-technical-writing` | pstack | 分层技术写作标准（Diátaxis + Google developer style + STE） | 内部引用 `unslop`（已带入，需改引用名） |
| `yxj-unslop` | pstack | 去掉文本里的 AI 腔 | 被 `teach`、`technical-writing` 引用 |
| `yxj-typescript-best-practices` | pstack | TS/TSX 读写时的最佳实践 | 前端主业，带 `references/patterns.md` |
| `yxj-wizard` | mattpocock | 生成交互式 bash 向导，带人走"只有人能做"的步骤 | 对角 `ops` playbook；产物落 `.work-docs/.../tmp/`（已改写） |
| `yxj-principle-boundary-discipline` | pstack | 校验/错误处理集中在系统边界，内部信任类型 | 无外部依赖 |
| `yxj-principle-type-system-discipline` | pstack | 让非法状态不可表示、语义原始类型打标、解析而非断言 | 引用 `typescript-best-practices` |
| `yxj-principle-encode-lessons-in-structure` | pstack | 同一句纠正出现第二次时，编码成 lint/元数据/运行时检查 | 对口"把经验固化进 skill/脚本"的习惯 |
| `yxj-principle-build-the-lever` | pstack | 非一次性工作先造工具（codemod/脚本/生成器） | 被 `attack-the-premise` 引用 |
| `yxj-principle-laziness-protocol` | pstack | 偏向删除与最小改动，抵制新抽象与信号穿透 | 与常驻的 ponytail 规则重叠，整合时二选一 |
| `yxj-principle-redesign-from-first-principles` | pstack | 新需求当成立项假设重新设计，而不是外挂 | 被 `attack-the-premise` 引用 |

## 2. 未保留的 11 个重复副本（已从仓库删除）

判定方法：对项目内每个 skill 名，在 `~/.pi/agent/skills/` 与 `~/.agents/skills/` 里找**同名且
`SKILL.md` 可读**的副本（含软链；`disable-model-invocation` 会让会话里的 skill 列表看不到它们）。

| 未保留项 | 全局可用实体 |
|---|---|
| `code-review`、`domain-modeling`、`research` | `~/.agents/skills/<name>/`（实体目录） |
| `dispatching-parallel-agents`、`finishing-a-development-branch`、`subagent-driven-development`、`systematic-debugging`、`test-driven-development`、`using-git-worktrees`、`verification-before-completion`、`writing-plans` | `~/.pi/agent/skills/<name>`（软链，目标存在且可读） |

### 一次误判与回滚

`requesting-code-review`、`receiving-code-review` 初判时也被移出，理由是"`~/.pi/agent/skills/` 下有同名软链"。
复核发现它们是**断链**：软链指向 `~/.agents/skills-disabled/`，该目录不在启用路径上，`SKILL.md` 不可读 ——
全局实际没有可用副本。两个 skill 已移回 `skills/`。教训：同名不等于重复，必须验证软链可解析且文件可读
（`[ -r <path>/SKILL.md ]`）。

- 这 11 个副本已从仓库删除，不再保留；如需恢复，从本文顶部列出的三个源库路径重新复制并重跑改造脚本。
- 代价：它们的 `## File boundary` 约束与引用改名随之失效，全局副本没有这段约束。恢复约束只有一条路：
  走 §0 的 A/B 路径，把需要的 skill 装回项目侧（**不修改全局副本**）。

## 3. 外部依赖现状

### 3.1 已复制进来的依赖（依赖闭包展开）

初版只按"能力"取舍，漏了被**显式跨目录引用**的依赖。改用闭包扫描后补入 6 个：

- `yxj-arena` —— 被 `yxj-architect`（`../../arena/SKILL.md`）与 `yxj-blast-radius` 引用。
- `yxj-principle-build-the-lever`、`yxj-principle-fix-root-causes`、`yxj-principle-laziness-protocol`、
  `yxj-principle-prove-it-works`、`yxj-principle-redesign-from-first-principles` —— 被
  `yxj-principle-attack-the-premise` 与彼此引用。

扫描覆盖 `(../)+<name>/` 任意层级（`references/` 子目录里是 `../../`），并对**已复制集合**做了引用改名：
`(../)+<原名>/` → `(../)+yxj-<原名>/`，`superpowers:<原名>` → `yxj-<原名>`。共 6 个文件被改写。
当前全部 `(../)+` 引用都能解析到存在的文件；`superpowers:` 前缀仅剩 2 处，指向未复制的
`writing-skills`（全局已有）与 `executing-plans`（与自研 `exec` playbook 重叠）。

### 3.2 无法复制、已就地标注的依赖

| 依赖 | 谁需要 | 为什么不能复制 | 处理 |
|---|---|---|---|
| `pstack-models.md`（Cursor 形式 `~/.cursor/rules/pstack-models.md`） | `architect`、`how`、`why`、`arena`、`interrogate` | 源库没有这个文件，它由未复制的 `setup-pstack` skill 生成，且绑定 Cursor 规则目录 | 5 个 skill 的 `SKILL.md` 各加了一段 `## External dependencies`：缺失时用当前会话模型，runner/reviewer 数量取默认 |
| `CONTEXT.md` | `codebase-design` | 是项目文档，不是发布物 | 已标注：只有任务要求时才创建，路径写进 contract |
| 项目侧规范文件（`CODING_STANDARDS.md`、`CONTRIBUTING.md` 等） | 原 `code-review`（未保留） | 属被审仓库自己的文件 | 随该 skill 一起不在本仓库 |

### 3.3 平台/工具耦合（未改，属整合范畴）

- Cursor 命名：`interrogate`、`how`、`why`、`arena` 里的 `Task tool`、`subagent_type: generalPurpose`；
  `architecture.md` 说 Pi 用子 agent 名。整合时要替换成 Pi 的子 agent 调用方式，否则会指挥出不存在的工具。
- `setup-pstack` 的角色模型清单（见 3.2）。
- 外部命令：`wizard` 需要 `gh secret`、可选 `shellcheck`；`prototype` 假设项目有 `pnpm` / `bun` 任务入口；
  `create-verification-skill` 提到 `tmux`。

## 4. 未取用 42 个（三库合计 80 − 保留 27 − 未保留 11），分类与理由

本节按能力取舍；被其它 skill 显式跨目录引用的，都已通过依赖闭包补入（见 §3.1）。

### 4.1 pstack 未取 26 个

- **平台耦合，本环境跑不起来**：`recall`、`reflect`、`no-comments`、`automate-me`（依赖
  `~/.cursor/projects/*/agent-transcripts`、`Comment Sicko` subagent、内置 `create-skill`）、
  `make-bot-ui`（Grok Bot webhook）、`setup-pstack`（pstack 自身配置）。
  **概念可借鉴**：`recall`≈你的 handoff、`reflect`≈把会话经验回写 skill、`automate-me`≈persona/mode 维护。
- **同能力或同机制重复**：`tdd`、`swarm`、`figure-it-out`、`maintain-verification-skill`、`show-me-your-work`。
- **个人风格**：`poteto-mode`（你已有自己的 mode）、`bro`（把上条消息去术语复述）。
- **其余 13 条原则**（未取，源库仍在）：
  `exhaust-the-design-space`、`experience-first`、`foundational-thinking`、`make-operations-idempotent`、
  `migrate-callers-then-delete-legacy-apis`、`minimize-reader-load`、`model-the-domain`、
  `never-block-on-the-human`、`outcome-oriented-execution`、`separate-before-serializing-shared-state`、
  `sequence-verifiable-units`、`subtract-before-you-add`、`test-behavior-not-implementation`。

### 4.2 superpowers 未取 5 个

`brainstorming`、`writing-skills`（全局已有同名，避免两套同触发）；`executing-plans`（与自研 `exec` 阶段重叠）；
`using-superpowers`、`diagnosing-superpowers`（superpowers 框架自身的引导与自诊断，你不需要整套框架）。

### 4.3 mattpocock 未取 11 个

- 依赖 issue tracker 配置（当前无此基建）：`to-spec`、`to-tickets`、`triage`、`wayfinder`、`setup-matt-pocock-skills`。
- 同能力或同阶段：`implement`（同 `exec`）、`diagnosing-bugs`（同 `systematic-debugging`，但它的性能回归诊断与
  `scripts/hitl-loop.template.sh` 值得单独取）、`grill-with-docs`（全局 `grilling` 已覆盖拷问，MP 版多了 ADR/术语产出）、
  `improve-codebase-architecture`（与 `codebase-design` + `domain-modeling` 重叠）、`tdd`（三库同类）。
- `ask-matt`：MP 生态的路由器，与 `yxj-work` 自己的路由冲突。

## 5. 文件目录规范改造（已完成，附验证）

依据 `docs/file-boundary.md`（唯一规范）：工作流产物只能落 `<execution-root>/.work-docs/tasks/<task-id>/`，
其中 `<task-id>` 是完整目录名 `{YYYYMMDD}-{NN}-{slug}`（如 `20260928-01-yxj-work-independent-workflow`），
分 `outputs/`、`evidence/`、`audit/`、`tmp/`；项目代码与项目文档属"任务目标"，可原地改但路径要先写进 contract 与 evidence。

### 5.1 统一边界块

保留的 27 个每个 `SKILL.md` 都插入了一段 `## File boundary`（另有 11 个在删除前也已完成同样改造，但随之失效），
声明输出根、目录分工、任务目标文件的例外、第三方 skill 写入前后要清点文件。校验：每个文件恰好一份块、
块后有空行；块文本刻意不写出规范里的禁用路径字面，否则会触发 `check-repo.sh` 的 forbidden grep。

### 5.2 就地改写的产物路径

| skill | 原落点 | 现落点 |
|---|---|---|
| `yxj-writing-plans`（未保留） | `docs/superpowers/plans/*.md`（3 处） | `.work-docs/tasks/<task-id>/outputs/plans/*.md` |
| `yxj-subagent-driven-development`（已移出） | `<repo>/.superpowers/sdd/<slug>/`（脚本常量 + 注释 + 正文示例，8 处） | `<repo>/.work-docs/tasks/sdd-<slug>/` |
| `yxj-create-verification-skill` | `.cursor/skills/verify-<app>/`（3 处） | `.pi/skills/verify-<app>/` |
| `yxj-prototype` | 未指定 | 补明：原型产物写 `.work-docs/tasks/<task-id>/tmp/`，要保留才移入项目 |
| `yxj-wizard` | "a scratch or `scripts/` path" | `.work-docs/tasks/<task-id>/tmp/`；要长期保留才进 `scripts/` |
| `yxj-principle-*` 全部 | — | 由统一块覆盖 |
| `yxj-codebase-design` | —（补例外说明） | `CONTEXT.md` 属项目文档：路径先写进 contract 与 `evidence/` |

### 5.3 验证证据

- `bash scripts/check-repo.sh` → `passed`。
- 旧路径残留扫描：`docs/superpowers`、`.superpowers`、`.cursor/skills` 在 `skills/` 下 0 命中。
- 边界块覆盖：保留 27/27，均为 1 份。删除的 11 个已无法验证，不列入。
- `sdd-workspace` 实跑（临时 git 仓库 + 两个同名 `plan.md`）：同一 plan 幂等解析到
  `.work-docs/tasks/sdd-plan`；同名 plan 隔离到 `sdd-plan-beta`；`plan-path` 标记与 workspace 内
  自忽略 `.gitignore` 生效；除测试造的文件外无任何写入落在 `.work-docs` 之外。三个脚本 `bash -n` 通过。
- 引用改名：6 个文件，`(../)+<原名>/` 与 `superpowers:<原名>` 均解析到存在目标。
- 相对路径瑕疵修正 2 处（`yxj-why` 的 `references/epistemics.md`、`yxj-typescript-best-practices` 的
  `patterns.md` 里指向 `../SKILL.md`）。

## 6. 给整合 Agent 的接口事实

1. **工作根与产物**：`yxj-work` 把工作流文件收敛到 `<cwd>/.work-docs/tasks/<task-id>/`，分
   `evidence/`、`outputs/`、`audit/`、`tmp/`。外部 skill 的产物落点若不同，必须映射或改写（见 §5.2）。
2. **阶段词汇**：playbook 名为 `fast-answer`(L0)、`investigate`、`research`、`design`、`plan`、`exec`、
   `bugfix`、`review`、`ops`、`mixed`。新 skill 应挂到这些阶段上，而不是另起一套流程。
3. **纪律已在自研侧**：done gate、required/optional 验证分层、`calls_since_progress` 预算、两级熔断
   （同命令同错误 2 次 / required 验证连续 3 次）。外部 skill 里的同类规则要**对齐阈值**，不要保留第二套数字。
4. **触发方式**：`yxj-work` 三个 skill 都是 `disable-model-invocation: true`（只作为用户手动 `/命令`，
   永不进模型技能列表）。保留的 27 个里有若干带同样标记，整合时要想清哪些该"模型可自动触发"。
5. **安装**：改 `scripts/install.sh` 白名单 + `scripts/check-repo.sh` 的校验清单，才能随仓库安装；
   `check-repo.sh` 还会在 `skills/` 全目录 grep 一批禁用路由串（清单见脚本），外部文本里出现就会门禁红。
6. **命名**：`yxj-work/playbooks/research.md`（playbook 文件）与 `skills/yxj-research/`（独立 skill）
   是两回事；后者未纳入本仓库。

## 7. 未完成事项

- `skills/yxj-work/playbooks-en-backup/`：上一轮"把 playbooks 译成中文"任务的原文备份，翻译尚未执行。
  确认新任务后应删除它，或先完成翻译再删。
- 与全局重复的 11 个 skill 已不保留在本仓库（见 §2）；本项目只维护自研与源库独有的 skill。
- **全局断链（仅记录，不操作）**：`~/.pi/agent/skills/` 下有 3 条断链
  （`requesting-code-review`、`receiving-code-review`、`hallmark`），软链目标在 `~/.agents/skills-disabled/`。
  这是本次操作之前就存在的环境状态，本仓库不处理全局目录。
- `yxj-teach` / `yxj-technical-writing` / `yxj-blast-radius` 内部对 `how`、`why`、`unslop` 的**裸名**引用
  未改名（`how` / `why` / `teach` 都是普通英文词，裸替换会误伤），需人工建立别名映射。
