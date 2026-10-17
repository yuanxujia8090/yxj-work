# 02b skills-main 对比与合并建议

> 对象：`skills-main.tgz`，即 Matt Pocock 的 skills，package 版本 1.3.1。共 38 个 SKILL.md，合计 168,114 B，分 engineering / productivity / misc / in-progress / deprecated 五个桶。
> 用户说明：这是一套和 x-rail 类似、平时在用的技能，可以考虑合并进 x-rail。v3-goal §一 也已经写明："优秀编程技能：/Users/yuanxj/Downloads/skills-main""编程相关技能可以糅合 pstack 和 skills-main 中的技能"。

## 1. 先看事实：用户本机已经在用其中一部分

- 会话中读取的路径是 `/Users/yuanxj/.agents/skills/<name>/SKILL.md`。**推断**：skills-main 通过 `scripts/link-skills.sh` 软链到了 `~/.agents/skills`。
- 主会话里实际 `read` 这些技能的次数：

  | 技能 | 读取次数 | 会话数 |
  |---|---|---|
  | code-review | 11 | 6 |
  | domain-modeling | 2 | 2 |
  | implement | 2 | 1 |
  | research | 1 | 1 |
  | tdd | 1 | 1 |
  | writing-for-agents | 1（加 SKILL-MECHANICS 1） | 1 |

- 字符串 `grilling`、`domain-modeling`、`research` 在会话 JSONL 里各出现约 186–192 次，但实际读取次数很少。**推断**：pi 把这些技能的描述放进了每轮的技能清单，所以它们每轮都占上下文，却很少真正被调用（**待确认**：pi 是否扫描 `~/.agents/skills`）。
- 同一能力存在多套重复技能：
  - TDD：superpowers `test-driven-development` 读 24 次；skills-main `tdd`；pstack `tdd` 在会话里被引用 9 次。
  - 评审：superpowers 的 `requesting-code-review` / `receiving-code-review`，和 skills-main 的 `code-review`。
  - 需求澄清：superpowers 的 `brainstorming`（读 30 次），和 skills-main 的 `grilling`。

  这些重复正是 01 问题 3 所说"规则竞争"的一部分。

## 2. 与 x-rail、pstack 的定位对比

| 维度 | skills-main | pstack | x-rail v3（目标） |
|---|---|---|---|
| 定位 | 日常工程技能的小积木，每个 0.2–12 KB | 自主长任务的工作方式加编排 | pi 上可续跑、能自动降级的长任务工作流 |
| 人机关系 | 大量 HITL 环节：grilling 一轮轮提问；to-tickets 让用户确认拆分；tdd 让用户确认 seam | never-block-on-the-human | 关键决策集中在开头的 Frame 阶段问，之后自主执行 |
| 状态存储 | issue tracker（GitHub/GitLab/本地 `.scratch/` markdown） | 本地 store（TSV/JSON） | 本地 `.work-docs/runs/`（TSV 加 Markdown） |
| 子代理 | research 用后台代理；implement-spec 用最大并发的 implementer 加 merger；code-review 用两个并行 reviewer | cloud worker 加跨模型 verifier | 主会话单写入，子代理按需使用且有时间盒 |
| 稳定性 | 无，交给 harness（见 `.out-of-scope/subagent-recursion.md`） | 依赖 Cursor | 自带 pi 扩展（failover、run-guard） |
| 写作方法论 | `writing-for-agents`：context pointer、两种负载、信息层级、完成判据、leading word、正向表述、剪枝 | principle-* | 采纳 skills-main 的写法作为 x-rail 文档规范 |

**最关键的一致点**：skills-main 明确主张"递归和失控由 harness 负责，不写进技能文字"。这和本方案"稳定性下沉到宿主层"（03 §1）完全一致，可以作为 v3 的设计依据。

## 3. 合并决策

> **单一来源规则（2026-10-17 用户新增）**：x-rail v3 是唯一来源。下面"吸收"的技能中，凡是 x-rail 已经真正覆盖其能力的，全局那份在 x-rail v3 安装并验证后归档（07 批次 B）：handoff、retro、implement、implement-spec。"引用"的技能因为被 x-rail 调用，所以保留。完整映射见 07 §2.1 和 §2.2。

决策分三类：**吸收**（把概念写进 x-rail，每条不超过几行）、**引用**（x-rail 在某一步明确要求"调用 Skill 工具 X"，复用已安装的技能）、**不合并**。

### 3.1 吸收进 x-rail（写入阶段卡或规范）

| 来源 | 吸收的内容 | 落在 x-rail 哪里 | 理由 |
|---|---|---|---|
| `writing-for-agents` | context pointer 要措辞精确；区分 context load 和 cognitive load；信息层级（步骤 > 文件内参考 > 外置参考）；每一步都有清晰、有要求的完成判据；leading word；正向表述，少用禁令；剪枝（单一真相源、环境即真相、删除 no-op） | `docs/authoring.md`（x-rail 自身文档规范），外加 CI 体量检查 | 直接针对 01 问题 3：执行路径约 71 KB，且多是禁令式规则；也呼应 v3-goal"不要用更多文字解决模型无法遵循的问题" |
| `ask-matt/PHASE-BOUNDARIES.md` | 只在阶段边界决定上下文怎么处理，中途压缩会丢线索；五种选择 continue / clear / handoff / subagent / compact，按顺序取第一个"是" | run-guard 的"单元边界上下文策略"（03 §7） | 和"单元边界主动压缩"设计一致，并且给出了决策顺序 |
| `to-tickets` | 竖切的 tracer-bullet 单元；每个单元能单独验证；**大小以一个新上下文窗口能装下为准**；显式写出 blocking 边；大范围重构走 expand–contract | Plan 阶段卡的拆分规则；units.tsv 的 `deps` 列 | 补足 pstack sequence-verifiable-units 的具体做法；符合用户"按复杂度而非数量拆分"的纠正 |
| `implement-spec` | 任务图加 frontier；用 context pointer 通信，不复制信息；一个集成分支，每个 implementer 一个 worktree | Execute 阶段卡和 Brief 模板的 CONTEXT 字段 | 和现有 frontier 实现一致；"只给指针"可以降低子代理上下文（`bbf04de5` 上下文达到 295,801 tokens） |
| `diagnosing-bugs` Phase 1 | 先建一个 **tight、可变红** 的反馈回路（一条已运行过的命令），没有回路就不进入假设阶段 | bug 路由的完成判据；04 回放评测的方法 | 判据可检查；回放评测本身就是这样一个回路 |
| `handoff` | 不重复已有工件，只引用路径；写明 suggested skills；脱敏；放在仓库外 | 恢复胶囊和终止 handoff 的格式（03 §6） | 胶囊限制在 2 KB 以内，正需要"只放指针" |
| `grilling`（方法）/ `loop-me` | 按轮次提问，每题附推荐答案，用户回答"yes"即接受推荐；能查到的事实由代理自己查，不问用户；**push right**：人工检查点尽量后移，并呈现一份 brief | Frame 阶段的澄清方式；结束时的交付 brief | 和 never-block 结合：一次性问清楚，之后不再打扰 |
| `retro` | 复盘时优先找"自动检查"而不是"多写规则"；分类为导航、自动检查、编码规范、no-op、工具经济性、信息获取 | run 结束的 Reflect 步骤 | 防止规则沉积（sediment） |
| `.agents/invocation.md` | 区分 user-invoked 和 model-invoked；依赖关系写成"调用 Skill 工具 X"，不写跨目录相对链接 | x-rail 路由与 SKILL frontmatter 规范 | 提高按需加载的命中率，避免模型自己去猜 |

### 3.2 引用（不复制，x-rail 在对应步骤调用已安装技能）

| 技能 | x-rail 在哪一步调用 | 改造 |
|---|---|---|
| `tdd` | Execute 阶段中的行为改动单元 | 原文要求"seam 先和用户确认"。在 x-rail 自主模式下改为：seam 写进 decisions.tsv；只有涉及单向门（公共接口或数据模型）时才写入 gates.md |
| `code-review` | Review 阶段（两轴：Standards 加 Spec） | reviewer 子代理跑在**另一模型家族**上（借鉴 pstack），有时间盒，并且必须有 fixed point（单元起点的 SHA） |
| `diagnosing-bugs` | bug 路由 | 原样使用 |
| `research` | 需要外部事实时 | 作为只读子代理，硬超时 15 min，可与其他只读子代理并行（最多 5 个），结果写入 run 目录 |
| `domain-modeling` | Frame 阶段涉及领域术语时 | 原样使用 |
| `grilling` | Frame 阶段的前置问答 | **由"吸收"改为"引用"**：x-rail 调用这个技能，所以保留全局技能。自主模式下只在 Frame 阶段提问，每题附推荐答案；问题数有上限（见 §3.4） |
| `codebase-design` | 间接依赖（tdd 会调用它） | 原样使用。v3 worktree 中的镜像副本 x-codebase-design 不安装 |

### 3.3 不合并

| 内容 | 原因 |
|---|---|
| `setup-matt-pocock-skills`、issue tracker 发布（GitHub/GitLab）、`triage`、`pr`、wayfinder 的远端 map | v3-goal §八 禁止"对外发布"；x-rail 状态只放在本地。wayfinder 的思路（一次只解决一个决策、fog of war）只作为大规模**规划**的可选参考，map 存成本地 markdown，不默认启用 |
| `teach`、writing-* 系列、`to-questionnaire`、`wizard`、`prototype`、misc 和 in-progress 桶 | 与 x-rail 的编码长任务无关；misc 桶已冻结 |
| Claude 插件打包（`.claude-plugin`、changesets、release workflow） | pi 不用这套机制 |
| grilling "不限问题数"（`.out-of-scope/question-limits.md`） | 与长任务的自主执行冲突。x-rail 只在 Frame 阶段提问，之后改用 gate 加默认值 |
| `implement-spec` 的"最大并发后台 implementer" | 本地证据显示子代理有 17.7% 失败、30 min 超时，中途无法 fallback。并发上限由 x-rail 控制，默认串行 |
| "不写 em-dash"等仓库格式规则 | 与 x-rail 无关 |

## 4. 与 pstack 风格设计的冲突和裁决

| # | 冲突 | skills-main 立场 | pstack 立场 | v3 裁决 |
|---|---|---|---|---|
| K1 | 何时问人 | 多处 HITL：确认 seam、确认拆分、grilling | 不阻塞人 | **前置并集中**：Frame 阶段一次性问清单向门决策，每题附推荐答案；执行期遇到问题写 gate、带默认值、继续做别的单元；结束时给一份 brief（push right） |
| K2 | 状态放哪里 | issue tracker | 本地 store | 本地 `.work-docs/runs/`。可选导出成 issue，需用户手动触发 |
| K3 | 子代理默认程度 | 研究和评审默认后台；实现最大并发 | 默认委派 cloud worker | **已确认**：≥ 5 个单元走子代理驱动执行，< 5 个由主会话执行；只读子代理并发 5，写入子代理 2；一个文件集只有一个写入者，各用独立 worktree（03 §10） |
| K4 | 评审 | 两轴、并行、同一 harness | verifier 用不同模型家族；单命令验证时不另设 verifier | 两轴审查加跨家族模型；低风险单元只看 ledger 里的命令证据 |
| K5 | 上下文策略 | 只在阶段边界决定；compact 是兜底 | 新代理优先，不靠 resume | 单元边界执行 PHASE-BOUNDARIES 决策树；压缩内容使用脚本生成的胶囊；子代理默认重新派发 |
| K6 | 技能组织 | 很多小技能，用"调用 Skill 工具"串联 | 一个大入口加 playbooks 加 principle 技能 | 一个小入口，加阶段卡，加对少数已安装技能的显式调用；不新增全局技能 |
| K7 | 递归和失控 | 交给 harness | 交给 Cursor | 交给 pi 扩展和 pi-subagents 配置（maxDepth、timeoutMs、toolBudget） |

## 5. 技能治理建议（初稿；最终方案以 `07-本机技能清理方案.md` 为准）

> 单一来源规则下，另有 11 个全局技能被 x-rail v3 取代，在 07 批次 B 中归档：superpowers 的 6 个，加上 using-git-worktrees、handoff、retro、implement、implement-spec。

> 07 已根据 pi 1.1.0 的加载器源码和使用次数，把 superpowers 中重复的技能改为**归档**（不再只是"仅手动"）。如果下表与 07 不一致，以 07 为准。

> 只是建议，不直接修改全局技能（v3-goal §六）。用户批准后再执行。

| 技能 | 来源 | 建议 | 理由 |
|---|---|---|---|
| tdd | skills-main | **保留**，作为唯一 TDD 参考 | 简短（3.6 KB），讲 seam 和竖切，与 x-rail 的单元模型一致 |
| test-driven-development | superpowers | x-rail 运行期间**仅手动** | 与上面重复；读 24 次，规则竞争 |
| pstack tdd | pstack 本地副本 | 仅手动 | 重复 |
| code-review | skills-main | **保留**，作为 Review 阶段标准 | 已在用（11 次） |
| requesting-code-review / receiving-code-review | superpowers | 仅手动 | 重复 |
| grilling | skills-main | 保留，只在 Frame 阶段调用 | 方法比 brainstorming 轻 |
| brainstorming | superpowers | x-rail 运行期间不触发（仅手动） | 读 30 次，带有硬门禁式流程，与 x-rail 路由冲突 |
| using-superpowers | superpowers | x-rail 运行期间不触发 | 读 53 次（35 个会话），"必须先调用技能"的规则与 x-rail 入口竞争 |
| writing-for-agents | skills-main | 保留，用于编写和维护 x-rail 自身 | 作为文档规范来源 |
| diagnosing-bugs、research、domain-modeling | skills-main | 保留 | 被 x-rail 引用 |

**待确认**：pi 是否支持让技能只能手动调用（类似 `disable-model-invocation`），以及具体的配置方式。如果不支持，替代方案是在 pi settings 中把这些技能移出自动加载目录。这需要用户批准。

## 6. 合并方式与版本

- 不把 skills-main 的文件复制进 x-rail 仓库。x-rail 在 `references/external-skills.md`（不超过 1 KB）中记录依赖的技能名、版本（skills-main 1.3.1）和用途，并由 self-check 校验这些技能存在。
- 吸收进来的概念用 x-rail 自己的话写，每个阶段卡里最多 3–5 行；需要细节时，用"调用 Skill 工具 X"的方式指向原技能。
- skills-main 升级时，只需检查 `references/external-skills.md` 中列出的 7 个技能（tdd、code-review、diagnosing-bugs、research、domain-modeling、grilling、codebase-design）是否发生了行为变化（06 阶段 P5 的回归任务）。
