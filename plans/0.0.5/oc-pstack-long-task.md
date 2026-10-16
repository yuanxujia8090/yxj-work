# oc-pstack 大任务方法论：结论与可借鉴点

> 状态：分析完成，仅归档结论；尚未对本仓库工作流做出改动。
> 编写日期：2026-10-16。
> 分析对象：`/Users/yuanxj/Downloads/plugins-main/pstack`（poteto 出品的 Claude Code 插件）。
> 关联文档：[README](README.md)（Pi 长会话延迟分析）、[优化方案](优化方案.md)、[验收与证据](验收与证据.md)。

## 结论先行

pstack 应对大任务的核心不是"让单个 agent 更能扛"，而是三条公理：

1. **长任务 = 一串短会话接力**：状态外置在文件里（units.tsv / ledger.tsv / decisions.tsv / resume note），会话只是执行载体。
2. **主线程只做编排和摘要**：大 payload（截图、大输出、长 transcript）全部路由给子代理，主线程只留摘要。
3. **没有独立验证的产出不存在**：合并/落地前必须由独立 swarm 给出 VERIFIED 裁决；inconclusive 不算过。

对照结论：0.0.5 分析的 Pi 会话暴露的问题（上下文膨胀、串行轮次、纯时长无谓词），本质都是违反了这三条。

## 一、大任务的处理矩阵（按规模分档）

| 规模 | 机制 | 核心承诺 |
|---|---|---|
| 单会话能完成 | 直接做 | 不启用重型机器（playbook 主动路由回轻路径） |
| 大迁移 / 无人值守 | `figure-it-out` + overnight contract | 先设计 workflow 本身当交付物，再执行 |
| 过夜单一任务 | `autonomous-run` + `/loop` | 可证伪完成条件 + 每轮最小变更验证 |
| 队列（独立 PR） | `autopilot-full` | 一 PR 一 owner 全生命周期；合并需 swarm 干净裁决 |
| 队列（耦合 / 要人看） | `autopilot-stack` | 同上，但只堆栈不落地，人早上一键 land |
| 多天程序 | `orchestrate` | 常驻 coordinator：只写 brief 不写代码，own 整个 program |

关键设计：`orchestrate` 被明确标注为 "deliberately heavy machinery"——单 agent 一个会话能完成的，playbook 会主动把用户路由回 overnight contract。**懂分档、不滥用重型流程本身就是核心。**

## 二、五个核心机制 × Pi 会话问题映射

### 1. 上下文守护（对应 354K 膨胀）

- `principle-guard-the-context-window`：截图 / 大文档 / 大输出路由给 subagent，主线程只留摘要；repo 常量内联避免重复 read；每 phase 限制文件数 + 轮预算。
- **Fresh subagents by default**：不用 resume-chain 拉长子代理（"interrupt-chained resumes silently drop directives"），scope 变了就合并后开新的。
- **状态外置**：`units.tsv` / `ledger.tsv` / `frontier.json` / `standing orders` / `resume note`。原则："只存在于上下文里的状态，等于不存在"（VM 死了它就没做过）。
- **`session-pickup`**：新会话从文件接手；长 transcript 交给子代理解析，主线程只拿 reduced timeline。
- 映射：Pi 单会话 250 轮、34K→354K，缺的就是"外置 + 接力"。压缩阈值 888K（contextWindow 1,044,480 − reserveTokens 156,672）从不触发是最后一根稻草；pstack 的做法是**不靠压缩救场，靠主动切片**。

### 2. 滚动窗口并行（对应 230/250 轮单调用串行）

- `swarm`：Frame（done predicate + 切片/赛马形状 + N）→ Fan out（**一条消息**批量 spawn，brief 完全自治：目标/范围/验证方法/报告格式）→ Aggregate（不带 SHA/方法的结果丢弃 respawn 一次）→ 一份合并报告。
- Rolling window：上限约 10 个在飞，**完成即补位**。原文："Blocking batches pay the slowest child of every batch"——正是 4 轮 900s+ 的病根。
- Completions 是**队列事件不是中断**：批量 drain，不在线程里 inline 深审。

### 3. 熔断与 liveness（对应 5 次 error 浪费 + 无卡死检测）

- "连续几次工具 abort 后停止重试，写 terminal handoff 到持久状态"——对应 Pi 会话中 5 次 error 空响应浪费约 10.5 分钟，按此纪律可秒级止损。
- 审计 tick（每小时，`/loop` 驱动）：**只数副作用为进度**（commit / push / check delta / 报告）；超期无副作用 = stuck，立即替换，不等礼貌返回。
- 每单元 timebox：到期返回部分发现直接停，不硬跑。

### 4. 验证制度（对应"验证靠自觉"）

- `swarm-verify` 每轮：多条独立 lane（重跑 gates / 真实表面 live 验证 / diff 审计 ≥2 lane / 对 trunk 的 regression lane），聚合成 **VERIFIED / NOT VERIFIED / INCONCLUSIVE** 三值——**inconclusive 不算过**。
- "通过得太容易时，先怀疑观测方法，再怀疑系统。"
- 每单元一个可验证小步（`sequence-verifiable-units`）：green 才前进，stacked PR 让顺序自证。
- 映射：Pi 会话没有可证伪完成谓词，所以 3h46m 无中间里程碑。pstack overnight contract 直接点名：**"a duration is not a finish condition"**。

### 5. 人机契约（对应"什么时候该问人"）

- `never-block-on-the-human`：可逆操作（写代码 / 拆任务）直接做不阻塞；仅不可逆（force-push / 删生产 / 对外发消息）确认。
- **state-then-wait**：操作者说"说说计划"≠ 开始干；stop 命令即时全场零写入。
- `pause-safely`：停在工作安全边界 + `wip:` commit + 写 resume note（`/tmp/<slug>-resume.md`），压缩临近时主动写。

## 三、可借鉴到本仓库工作流的 6 条（按优先级）

1. **切片纪律 > 压缩调参**：ctx 到约 150K 主动停，写 resume note 文件，新会话 pickup。把压缩线从 888K 调到 150K 只是治标。
2. **落实"只数副作用"**：长跑任务每轮必须产出 commit / 文件 / check delta；连续 2 轮无副作用 = 判 stuck，换策略或换模型，不继续空转。
3. **大任务先 framing 再动手**：写可证伪完成谓词 + 阶段列表 + 每阶段验证方法，作为"设计 workflow"的交付物。pstack 里这是硬前置。
4. **扇出要滚动不阻塞**：独立子任务批量 spawn（一条消息 N 个），完成即补位；这是 900s 长轮的真正解药——比降 thinking 优先级更高。
5. **熔断硬编码**：连续 2–3 次同类失败 → 停、写失败上下文、交人 / Oracle；不要"再试一次看看"。
6. **教训结构化**：反复出现的错误编码成 gate / lint / check / script（`encode-lessons-in-structure`），而不是每次靠提示词提醒。pstack 连"每小时重读 playbook 防漂移"都写进了流程。

## 四、一句话总结

pstack 对大任务的信仰：**agent 的可靠性来自制度（切会话、外置状态、独立验证、滚动并行、硬熔断），不来自单个模型的耐力**。Pi 会话的 3h46m 是"信任模型耐力"的典型样本；pstack 会把它变成 10 个约 20min 的新鲜子会话 + 一个只读摘要的协调线程。

## 五、证据来源（pstack 关键文件）

- `skills/poteto-mode/SKILL.md` + `playbooks/`：orchestrate.md、multi-phase-plan.md、autonomous-run.md、session-pickup.md、pause-safely.md、autopilot-full.md、autopilot-stack.md、babysit.md、hillclimb.md。
- `skills/principle-guard-the-context-window/SKILL.md`、`skills/principle-sequence-verifiable-units/SKILL.md`、`skills/principle-never-block-on-the-human/SKILL.md`。
- `skills/swarm/SKILL.md`、`skills/figure-it-out/SKILL.md`。
- `docs/guide/07-overnight.md`、`docs/guide/README.md`。

未深读的可选项：`show-me-your-work` 全文（decisions.tsv 六列格式）、`orchestrate.md` 完整版、`automations/benny/`。
