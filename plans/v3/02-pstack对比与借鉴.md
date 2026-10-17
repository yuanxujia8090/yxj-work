# 02 pstack 对比与借鉴

> 对照对象：pstack 是 Cursor 插件 v0.15.15，只有 skills 加 2 个 agent，没有 hooks。它依赖 Cursor 的 `/loop`、Task 工具和云代理。v3 x-rail 指当前 `v3.tgz` 中的版本。
> 原则（v3-goal §八）：pstack 不是唯一正确答案。要借鉴的是它的机制，不照搬它的平台假设（云代理、Cursor Task）。

## 1. 体量与结构

| 维度 | pstack | v3 x-rail（现状） |
|---|---|---|
| 入口 | `poteto-mode/SKILL.md` 20,563 B（路由加原则） | `SKILL.md` 4,568 B |
| 长任务核心 | `orchestrate.md` 16,779 B；`autonomous-run.md` 1,878 B；`pause-safely.md` 1,135 B；`session-pickup.md` 1,678 B | exec.md、execution、orchestration、recovery、work-items，执行路径合计约 71 KB |
| 记账工具 | `scripts/orch/orch.ts`：一条命令进、一行结果出；store 是 TSV/JSON | task.py 594 行，task_checks.py 754 行，另有 coordination、work_items、frontier 共 1,909 行；拒绝率 37% |
| 原则 | 30 个 principle-* 小技能，按需调用 | 内嵌在各个模块里 |
| 宿主依赖 | Cursor `/loop`、Task、cloud agent | pi 加 pi-subagents 0.76.1 |

**结论**：pstack 的入口也不小。它真正稳定的地方，在于长任务的状态保存在磁盘上，每个文件有固定格式；执行循环很短；失败按类型处理。这三点值得学，"大而全"的规则文本不值得学。

## 2. 逐项对比

| pstack 机制 | 它解决什么 | v3 x-rail 现状 | 借鉴决策 |
|---|---|---|---|
| **autonomous-run**：先写可检查的完成判据（predicate），循环到满足为止，每次迭代都做检查点 | 防止提前宣布完成，也防止停下来等人 | 有 Status/Evidence，但没有"循环直到判据满足"的驱动 | **采纳**。RUN.md 必须有可数的 Done 判据；续跑由扩展驱动（03 §5） |
| **figure-it-out**：Frame → 设计工作流 → 循环 → 审计轨迹 → 验证 | 不清楚的问题先定框架再动手 | plan 路由有类似内容 | **采纳为 Frame 阶段卡** |
| **orchestrate store**：preferences.md、units.tsv、frontier.json、ledger.tsv（按 head SHA）、inbox/、gates.md、decisions.tsv、派生的 status.md | 状态在上下文之外；可续跑；可审计 | 有 frontier/dispatch/notify/inbox/consume，加 coordination.json | **采纳精简版**：units.tsv、ledger.tsv、decisions.tsv、gates.md、events.jsonl，status 由脚本派生（03 §3） |
| **Brief 模板**：GOAL / SCOPE / CONTEXT / ACCEPTANCE / VERIFY / TIMEBOX / FORBIDDEN / REPORT / STANDING | 子代理拿到的信息完整，并且有时间盒 | 有 dispatch 模板，但没有 TIMEBOX，超时继承宿主的 30 min | **采纳**，并把 TIMEBOX 直接映射到 pi-subagents 的 `timeoutMs` |
| **Retry by mode**：cap-hit 缩小范围；network 原样重试；**tool-error 换模型重试**；unknown 重试 1 次；两次后放弃并重新规划 | 失败有界，不死磕 | 文档写明"不自动重试、不换模型" | **采纳**。这是 failover 设计的直接依据（04） |
| **约 70% 预算时停止派发，收尾已验证的部分** | 不会烧完预算却什么都没落地 | 没有 | **采纳**。run 预算到 70% 时进入 Landing |
| **永远不为了查看状态去 resume 一个代理**；僵尸对账 | 防止 resume 链丢失指令 | 有 resume 失败的实例：CR 任务 02:25 resume 1.1 min 后被拒 | **采纳**。默认重新派发一个新代理，带合并后的范围（fresh respawn），resume 只用于真正需要续写的情况 |
| **pause-safely**：wip commit 加上下文之外的 resume note | 中断后不丢进度 | 有 handoff，但最终提交没做 | **采纳**。每个已验证单元做一次检查点（03 §6） |
| **session-pickup**：轨迹是权威；不重做 | 续跑时不重复工作 | recovery 模块里有 | **采纳**。由胶囊加 ledger 判断哪些已经做完 |
| **show-me-your-work**：decisions.tsv 只追加，做跨模型审查 | 决策可审计 | 有 DECISIONS 段 | **采纳**。审查由另一模型家族执行（openai26 ↔ bai 互审） |
| **never-block-on-the-human**；升级清单写进 gates.md | 不停下来等人 | 有 14 次子代理请求主会话决策；31 次人工输入"继续" | **采纳**。gate 带默认值，遇到 gate 就去做其他单元（03 §8） |
| **make-operations-idempotent / sequence-verifiable-units** | 重放安全；每个单元可以单独验证 | work-items 部分做到了 | **采纳**。所有 `xr` 动词都幂等；每个单元都有 VERIFY 命令 |
| **验证分级**：只需一条廉价命令时，worker 自己跑；昂贵或高风险的单元才用另一模型家族的独立 verifier | 不搞形式化验证仪式 | playbooks/verification.md 有 24 KB | **采纳**。verification 变成"按需查阅"，默认只要求 ledger 有记录 |
| **recall / reflect** | 从历史会话中学习 | 没有 | **部分采纳**。run 结束时做 reflect，写入 preferences 和回放语料；recall 放到后续阶段（06） |
| **TDD 技能** | 先测试 | 全局有 3 套 TDD（superpowers、pstack、skills-main） | 只保留一套，见 02b |
| **cloud worker、Cursor /loop、watch-pr、Bugbot** | 平台能力 | pi 没有 | **不采纳**。用户已明确"云功能除外" |
| **默认多 worker 并行（prefer fewer, broader workers）** | 吞吐 | target-architecture 写了"默认主动委派" | **有条件采纳**，见下 |

## 3. 不照搬的地方，以及原因

1. **默认委派**（2026-10-17 用户已拍板，改为学习 pstack）。
   - pstack 默认派发 cloud worker。本地 pi 上原先有四个问题：
     - 子代理错误率 17.7%（53/300）；
     - 超时以模型时间为主（`bbf04de5` 20 分钟里有 18.0 分钟在模型上）；
     - 中途失败无法 fallback；
     - supervisor request 14 次。
   - 进一步分析发现，成功 worker 的中位时长是 6.8 min，失败主要来自"超时设得太短"和"中途无法降级"，两者都有对策。
   - **裁决**：
     - **≥ 5 个单元的大任务走子代理驱动执行**，主会话只做编排、合并和验证；< 5 个单元由主会话直接执行，对应 pstack 的"一个代理能做完就不上编排"。
     - 一个文件集只有一个写入者，各用独立 worktree，由主会话串行合并。
     - 只读子代理并发上限 5，写入子代理 2。
     - 时间盒按证据定为 worker 45 min、reviewer 25 min、只读 15 min，另按轮次和上下文控制单元规模。
     - 详见 03 §10。
2. **云端审查**。审查改用"另一模型家族、本地子代理"：openai26 写的代码由 bai/deepseek 审，反过来也一样。
3. **orch.ts 的 TypeScript 实现**。x-rail 现有 Python 工具链已经有 1,909 行。这次不换语言，只收敛对外的接口（03 §4）。
4. **30 个 principle 技能**。它们不作为独立技能安装（会加重全局技能竞争，见 01 问题 3），而是浓缩成阶段卡里各一行的要点。

## 4. 借鉴后 x-rail 与 pstack 的分工差异

- pstack 的稳定性一半来自 Cursor 宿主（/loop、Task 的超时和恢复）。pi 宿主没有这些能力，所以 x-rail v3 **必须自带两个 pi 扩展**：
  - failover 扩展：负责模型故障切换；
  - run-guard 扩展：负责续跑、压缩胶囊和停顿检测。
- 这部分是 pstack 里没有的新增工作，也是 v3 与 pstack 最大的不同（见 03、04）。
