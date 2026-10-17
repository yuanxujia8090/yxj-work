# PStack 设计参考：原则、判定、措施与 x-rail 适配

> 阅读日期：2026-10-16。
> 来源：本地 PStack 0.15.15 下载副本，位置 `/Users/yuanxj/Downloads/plugins-main/pstack`。
> 使用范围：仅在任务目标是修改或调整 x-rail 本身（技能、流程、脚本或文档）时，按需读取本文。
> 禁止用于日常执行：会话中仅调用、使用 x-rail 相关技能处理任务时，不读取本文，也不将其列为前置阅读或自动加载材料。
> 性质：源码阅读与设计分析，不是运行测试报告，不改变 x-rail 当前规则、授权或验收要求。

## 1. 怎么使用这份参考

先判断任务目标是否包含修改或调整 x-rail 本身。仅在符合这一范围时，按需查看[问题索引](#11-遇到问题时从哪里查)，再读相关原则、判定和原文，并按[适配方法](#12-怎样用这份参考调整-x-rail)检查。仅使用 x-rail 相关技能完成其他任务，即使执行中遇到问题，也不触发本文阅读。

全文区分三种内容：

- **原文要求**：技能、流程或脚本明确写出的行为，附来源。表达的是该版本设计，不代表模型每次遵守。
- **阅读归纳**：根据多个来源解释机制之间的关系，不冒充作者的历史动机或实际效果。
- **适配建议**：面向 x-rail 的建议，须另行决定与验证，不是已经实施的规则。

阅读基线有明确边界。该下载副本没有 Git 提交信息，不能写成某个已核实的上游提交。本文记录版本和内容指纹，引用本地原文件；日后原目录移动或来源升级，应按第 13 节重新核对。脚本测试的阅读说明“测试设计覆盖了什么”，不表示这次执行过测试。

**阅读归纳：PStack 的核心价值在于连接目标、理解、设计、执行、验证和反馈。** 流程选择、分工、证据和纠偏共同服务于可验证结果。只搬运任务表、代理数量或文档格式，不能完整保留这种连接。

## 2. 整体结构：从用户目标到可核对结果

像前端应用中路由、页面、组件和底层工具各司其职，PStack 也有几层职责。下表是阅读归纳，名称来自原文件，层次划分为本文整理。

| 部分 | 负责什么 | 主要来源 |
| --- | --- | --- |
| 入口 `poteto-mode`，即任务分流与工作风格入口 | 根据请求选择流程；声明原则触发、权限、代理和回复约束 | [主入口][entry] |
| `playbooks`，即按工作类型编排的流程 | 功能、修复、调查、性能、交付、恢复等，各自规定动作和结束位置 | [全部流程入口][routing] |
| 专项技能 | 解释代码、查历史原因、探索设计、比较候选、覆盖检查、审查与复盘 | [理解代码][how]、[追查原因][why]、[架构设计][architect]等 |
| 原则 | 遇到分歧时约束选择，例如先理解、减少复杂度、隔离共享写入、证明结果 | [原则入口][principles]及第 4 节 |
| 代理说明 | 给执行者统一工作风格；特定代理承担评论检查等职责 | [通用执行代理][agent]、[评论检查代理][comment-agent] |
| 脚本 | 将可机械判断的部分做成命令，例如计划结构、状态归档、代码托管平台状态观察 | [脚本边界](#9-程序实际保障什么哪些仍靠模型) |
| 宿主及外部工具 | 启动代理、安排唤醒、驱动浏览器或命令行、提供认证与代码托管能力 | [外部能力清单][external] |

**原文要求：** 用户表达目标、限制和完成条件，入口选择流程，并在步骤需要时读取相关技能。入口要求应用原则前完整读取对应文件，并说明原则具体改变了哪个选择。[入口与原则][entry]

**阅读归纳：** 一项任务大体经过下面的判断链，但不要求所有任务机械走完整链路：

1. 明确用户需要答案、方案、行为修改、诊断，还是实际交付操作。
2. 理解相关系统，区分“现在怎样运行”和“当初为何这样设计”。
3. 找出会影响选择的未知，用来源、复现或原型解决。
4. 选择数据结构、边界和工作组织，先确定怎样验证。
5. 以可核对的小单元执行，发现新事实后调整。
6. 对真实产物验证，检查证据仍对应当前输入，再按授权交付。
7. 将重复错误放到能防止复发的位置，检验改进是否改变实际行为。

不能从“常见路径”推出统一强制阶段。调查流程明确只交付答案；多阶段计划明确只交付计划；独立调用架构技能则默认会继续实施。调用上下文和流程结束条件都必须读取。[调查][investigation]、[多阶段计划][multi-plan]、[架构的继续与暂停][architect-agree]

## 3. 关键判定：什么时候走哪条路

### 3.1 按交付性质分流，不先给所有任务统一打等级

| 用户真正需要的结果 | PStack 原文选择 | 判断和边界 |
| --- | --- | --- |
| 有依据的解释、调查或推荐 | Investigation，调查流程 | 只读，不默认实现、开代码评审申请或持续监控 |
| 修正已有错误 | Bug fix，缺陷修复 | 先在对应真实入口复现，再用运行证据排除原因 |
| 新增或改变行为 | Feature，功能开发 | 理解系统、探索结构、检查工作拆分，委派实现并验证 |
| 调整结构但保持行为 | Refactoring，重构 | 先固定原行为，结构变化不能偷偷加入新功能或修复 |
| 一次性能问题 | Perf issue，性能诊断与修复 | 先获取有效基线，再从实际运行定位，不从源码猜收益 |
| 持续优化一个指标 | Hillclimb，逐次实验优化 | 先固定可信测量方法，一次改一个假设，测量后保留或撤销 |
| 需要证据选择方案 | Prototype，原型 | 用可丢弃实现解决可观察问题，避免让用户回答可实验确定的事实 |
| 仅定位运行异常 | Runtime / Trace forensics，运行现场或记录取证 | 产物是诊断；捕获记录与实时现场的观察边界不同 |
| 验证视觉还原 | Visual parity，视觉一致性 | 明确参考画面与实际结果，按对应表面检查 |
| 产出多阶段实施方案 | Multi-phase plan，多阶段计划 | 计划本身是交付；原文要求收到明确执行指令后再实施 |
| 已有变更需要达到可合并状态 | Babysit，持续处理检查和评审 | 先声明观察或推进模式，达到可合并位置就停；不自动授权合并 |
| 用户要求实际合并交付 | Shipping，交付合并 | 独立核验每项，从依赖链底部连续合并，遇验证缺口停止 |

这些判断来自[入口分流][routing]和[流程总表](#5-全部-23-类流程的职责与结束边界)。它们不是统一的“小／中／大”分数表。

### 3.2 分别判断理解难度、严谨程度和组织方式

PStack 在不同地方使用不同判断，不能揉成一个任务等级。

| 判断对象 | 原文依据 | 采取措施 |
| --- | --- | --- |
| 解释问题简单还是复杂 | 单模块、窄问题与跨系统问题；不确定时先选简单路径 | `how` 简单问题由一位解释者处理，复杂问题先分角度探索再综合；不是所有调查都多代理 [理解分流][how] |
| 任务需要多严格 | 不可逆程度、影响范围、已知阻塞与可观察完成条件 | `figure-it-out` 将严谨程度落实成检查和产物，低风险可逆步骤减轻 [定制流程][figure] |
| 采用一个执行者还是分工 | 前置、独立工作、共享状态和最小安全拆分 | 常规功能也要检查，并在阶段边界重判；单执行者最好时说明原因 [功能流程][feature] |
| 一个任务还是持续项目 | 能否在当前会话预算内由一个执行者完成；是否跨多日、很多交付项与执行者 | 单任务持续执行用 Autonomous run；需要定制流程用 figure-it-out；持续项目才用 Orchestrate [入口][routing]、[大型协调][orchestrate] |
| 能否省略额外验证者 | 验证是否只是一条廉价命令，还是需要复杂判断、成本高或影响大 | 大型协调流程中，前者由执行者运行并报告，后者使用独立验证者 [协调验证][orchestrate-verify] |

**重要纠正：** 常规 Feature 流程第 4 步明确要求委派代码编写，不允许用“改动小，写个原因就跳过”规避；原文给出的理由是分离实现与评审。禁止再生子代理的叶子执行者可以自己完成修改并保留相应分离。主入口也会将大范围任务导向更专门的流程。[功能流程][feature]

因此，“PStack 只有大任务才委派”不符合该版本原文。x-rail 可以选择不同政策，但应说清保留什么目的、由什么替代措施承担，而非把适配写成上游原规则。

### 3.3 初判不是一次性结论

PStack 没有在已读入口和脚本中提供统一的自动复杂度分类器。执行中调整主要依赖以下明确动作：

- 常规功能在阶段边界重写工作拆分检查。[功能流程][feature]
- 架构实施出现反复同类偏离、调用方泄露内部规则、类型被迫绕过检查等模式时，重新理解并设计；不能不断加补丁。[架构纠偏][architect-scrap]
- 大规模展开前跑通代表单元，检验任务说明、验证方法和单元大小。[代表单元][orchestrate-pilot]
- 试验结果否定假设时，停止保留该假设导致的修改。[缺陷修复][bugfix]、[逐次实验][hillclimb]
- 上游错误、验收失效或基础设施故障会污染整批工作时，停止继续扩散，修好原因再推进。[故障处理][orchestrate-failure]

**阅读归纳：** 这套设计限制误判损失的办法，是尽早得到能否定原判断的事实，并提供调整动作。它仍依赖模型识别信号，不能保证初判正确或每次及时纠偏。耗时、轮数和“看起来很大”不能替代这些事实。

## 4. 24 条原则：触发、措施和容易丢失的目的

以下为逐条中文转述。英文名称仅用来对应源码，不要求用户记忆；每条都链接到原文。表中“避免误用”为阅读归纳。

### 4.1 目标与理解

| 原则与来源 | 什么时候用 | 核心措施 | 避免误用 |
| --- | --- | --- | --- |
| [体验优先][p-experience-first] | 功能范围、体验和实现便利冲突 | 让每个选项服务核心流程，先验证体验；最终用户、调用者和维护者都算使用者 | 不能只优化开发者写起来方便，也不能以“体验”为由无限扩需求 |
| [先打基础][p-foundational-thinking] | 选择数据结构、安排阶段、处理并发前 | 先确定核心模型与访问方式；先做后续都会受益的基础工作；先去掉冗余 | 基础是为了后续成果，不是先建通用框架 |
| [围绕新条件重新设计][p-redesign-from-first-principles] | 新要求改变已有设计 | 假设新条件一开始就存在，重新看整体，再分步交付并同步引用 | 不是每次重写，也不应永远靠追加例外容纳变化 |
| [质疑共同前提][p-attack-the-premise] | 多次修补共享同一假设，却失败在同一位置 | 写出共同前提，统计问题集中在哪些执行主体，检查角色分配是否造成失衡 | 不能仅凭“又失败了”随意推翻一切；先用事实判断前提是否真是原因 |
| [修根因][p-fix-root-causes] | 缺陷、回归、重复异常 | 复现、追因、验证机制，检查同类调用；重启异常优先调查持久状态 | 加兜底掩盖症状不算修复；必要边界校验仍应存在 |
| [探索不同结构的候选][p-exhaust-the-design-space] | 陌生交互或有多种可行结构的架构选择 | 形成两到三个实质不同的原型或草图后比较 | 已有明确模式、机械修改、目标清楚的修复不强制多方案 |

### 4.2 简化、建模与边界

| 原则与来源 | 什么时候用 | 核心措施 | 避免误用 |
| --- | --- | --- | --- |
| [以最少复杂度取得结果][p-laziness-protocol] | 重构、抽象、增加层次或传递新信号 | 优先删除，合并重复决策，缩短无价值转发，保持一个事实来源 | 最小差异必须解决真实问题，不能跳过理解、验证或必要权限控制 |
| [先减后加][p-subtract-before-you-add] | 新增、重构、重写之前 | 先清掉死逻辑、重复验证、空引用和冗余提示，再建设 | 不等于未经许可删除用户内容，也不等于预防性大清理 |
| [降低阅读负担][p-minimize-reader-load] | 代码、规则或接口难追踪 | 同时减少要穿过的层和要记住的状态；让接口隐藏真正复杂度，缩小可变状态范围 | 文件少不等于易懂；一个全局状态很多的平面文件也很难读 |
| [把业务关系放进数据结构][p-model-the-domain] | 分支、布尔字段、状态与结构假设散落 | 用状态模型、带类别的数据、映射表或合适容器承载规则 | 不强迫抽象；结构应消除重复与非法组合，不能只换名字 |
| [校验放在边界][p-boundary-discipline] | 外部输入、配置、协议、框架适配 | 在入口解析和验证；内部使用已经验证的类型；业务逻辑尽量为输入决定输出的纯函数 | “信任内部”以边界确实建立保证为前提，不允许跳过不可信输入验证 |
| [让类型帮助排除错误][p-type-system-discipline] | 设计状态、函数签名与类型 | 不让互相矛盾的状态轻易构造；区分含义不同的标识；完整处理各种类别；从权威结构派生 | 不为精确而复杂化；类型转换不能代替证据或运行输入校验 |
| [迁完调用方再移除旧内部接口][p-migrate-callers-then-delete-legacy-apis] | 可协调修改、没有外部兼容承诺的内部重构 | 清点调用方，同一轮迁移并移除旧路；异常适配层须有边界 | 有外部用户或历史格式承诺时，不能照搬为无条件破坏兼容 |

### 4.3 执行与协作

| 原则与来源 | 什么时候用 | 核心措施 | 避免误用 |
| --- | --- | --- | --- |
| [先造能做事或证明结果的工具][p-build-the-lever] | 非平凡工作，特别是机械修改和核对 | 做最小脚本、生成器或统一执行说明；先试一个单元，再证明工具能复现；确定性工具可替代人工代理群 | 不应把脚本能一次做完的事情拆给多个代理，也不为两处显然修改搭框架 |
| [保护主会话材料容量][p-guard-the-context-window] | 大文档、日志、重复读取、并行规划 | 大资料留执行侧，主会话接收摘要；组织阶段与材料范围；高频必需内容就近提供 | 摘要不能清除已经读入的历史；也不能为了少字隐去失败和决策事实 |
| [先消除共享写入，再考虑串行锁][p-separate-before-serializing-shared-state] | 多人或多代理可能写同一对象 | 独立事实分别存储，到读取边界汇总；确实只有一个权威对象时，再以锁或唯一所有者串行 | 两人写同一文件的不同字段仍是共享写入；口头约定不等于并发控制 |
| [重复运行能收敛到正确结果][p-make-operations-idempotent] | 启动、生命周期、恢复、重复操作 | 像表单重复提交仍只产生一笔有效结果，检查重复执行和半途崩溃后的协调恢复 | 这是幂等性，不是允许盲目重试、清理现场或启动第二份相同工作 |
| [围绕目标终态推进][p-outcome-oriented-execution] | 有明确阶段边界的迁移和重写 | 可以接受预先声明、范围受控、可恢复的中间不完整状态；在明确边界证明最终结果 | 不能据此让生产任意损坏；需要阶段允许范围和最终完整验证 |
| [不要让人替执行者做日常推进][p-never-block-on-the-human] | 可逆且授权内的执行选择 | 作合理决定、推进并交付可审阅结果；产品方向和不可逆动作保留给用户 | 上游的自主权范围不能覆盖当前用户的费用、委派、发布和数据保护要求 |

### 4.4 验证与持续改进

| 原则与来源 | 什么时候用 | 核心措施 | 避免误用 |
| --- | --- | --- | --- |
| [证明真实结果][p-prove-it-works] | 交付、接受代理结果、报告成功前 | 核对实际值、实际进程和实际产物；可重复的脚本比一次口头核对更有力 | 编译通过、文件新、日志写了完成，都不等于用户结果成立 |
| [分成逐项可验证的工作单元][p-sequence-verifiable-units] | 多步改动、批量迁移与交付排序 | 每个单元有已知基线、一个变化和一次检查；顺序本身展示依据 | 不等于每行编辑都测试或每个文件一个代理；与允许计划性中间破坏的原则须在不同边界解释 |
| [测试用户可观察的行为][p-test-behavior-not-implementation] | 新写、修改、保留测试时 | 用具体输入调用真实对象，与明确预期比较；检查测试能否因缺陷而失败 | 关键词存在、只检查调用过、预期从实现本身计算，都可能空转；表间关系和编译期类型检查有各自价值 |
| [解释测量数字][p-explain-the-number] | 提速、回归、吞吐、行为评估结果 | 说明样本、波动与限制因素，排除错误、跳过工作、缓存和无效计时 | 局部材料更少不能直接推导总耗时更短；没有定位限制因素，不应武断报告因果 |
| [把重复教训放进结构][p-encode-lessons-in-structure] | 同一错误再次出现，或再次想补同一句提醒 | 优先架构、类型、规则检查和可复现测试；必须判断的才保留简短说明和失败例子 | 增加文字不是默认改进；检查只能查到它真正观察的内容 |

## 5. 全部 23 类流程的职责与结束边界

这是阅读导航，具体规则以各文件为准。表内明确保留不同流程的结束条件，避免从其中一条概括全局。

| 流程原名与中文说明 | 核心动作 | 交付或结束边界 |
| --- | --- | --- |
| [Investigation：调查][investigation] | 追踪事实，按需要解释或比较取舍 | 有依据的答案；不默认实现或开交付流程 |
| [Bug fix：修复][bugfix] | 真实入口复现、排除假设、确认机制、委派修复、同入口复验 | 原问题从失败到通过的证据；便宜本地路径才套专门先失败测试节奏 |
| [Feature：功能][feature] | 理解、设计、工作拆分检查、委派、真实验证 | 结果、设计选择、分工及未决事项；阶段边界重判 |
| [Refactoring：重构][refactor] | 固定原行为，先减后改，小步保持行为 | 行为等价证据；发现新功能或缺陷另分范围 |
| [Perf issue：性能修复][perf] | 基线、运行定位、最便宜有效策略、修复后测量 | 数字及其有效性；一次性解决问题 |
| [Hillclimb：持续指标优化][hillclimb] | 固定有效测量，一次一个假设，保留或撤销 | 达成目标，或剩余想法不值得成本时如实说明；不能改低目标冒充通过 |
| [Runtime forensics：现场取证][runtime] | 对活进程采集运行证据并解释 | 诊断，不偷偷转修复 |
| [Trace forensics：记录取证][trace] | 解析已捕获记录，定位时间、调用及机制 | 记录所支持的结论与限制；不假装持有现场 |
| [Prototype：原型][prototype] | 先写清需要观察什么，最小实现，运行比较 | 可以支持选择的证据；原型不是生产完成 |
| [Visual parity：视觉还原][visual] | 针对实际画面与交互做对照 | 可核对的一致性证据 |
| [Authoring a skill：编写技能][author] | 走宿主技能编写流程，核对元信息和引用，按需做结构用例 | 技能交付；减少无效文字，引用共同规则而非复述 |
| [Eval：行为评估][eval] | 自然任务、隐藏考核点、隔离环境、匿名结果评判、核对实际过程 | 对候选规则的采用建议；不以执行者自报证明有效 |
| [Multi-phase plan：多阶段计划][multi-plan] | 未知先原型，填可执行清单，检查结构 | 计划与检查结果；明确执行指令后才实施 |
| [Autonomous run：持续执行一个目标][autonomous] | 明确结束条件，事件或定时唤醒，小步验证、记录 | 达到条件或真正死路；平台唤醒能力另有依赖 |
| [Orchestrate：大型项目协调][orchestrate] | 分轨、代表单元、滚动派发、集中处理通知、验证、持续集成 | 核对所有执行者去向、实际终态和当前版本证据 |
| [Autopilot-full：独立交付队列][autopilot-full] | 每项一位负责人，执行到已授权合并；根协调者验证 | 独立项实际交付；不是所有项叠在一个依赖链 |
| [Autopilot-stack：顺序变更栈][autopilot-stack] | 将工作组织为连续可审阅的分支链，按该流程独立检查 | 交付用户后续合并的变更栈；区别于自动全部合入 |
| [Babysit：处理检查与评审][babysit] | 声明模式，按冲突、评审、自动检查顺序处理 | 达到可合并位置；不因状态全绿自动合并 |
| [Shipping：合并交付][shipping] | 独立核验、核对当前差异、只合并底部连续已验证部分 | 已合并事实与第一个缺口；实际合并需授权 |
| [Opening a PR：提交代码评审申请][opening] | 整理聚焦的说明、检查与证据 | 创建 Pull Request（拉取请求，即供评审和合并的代码变更申请）；不自动持续监控或授权合并 |
| [Session pickup：接续现场][pickup] | 重建先前意图和实际工作状态，明确下一动作 | 接续点交给对应执行流程；复用事实并核对产物，不从零重做 |
| [Pause safely：安全暂停][pause] | 安全节点停下，保存现场和接续第一步 | 明确暂停，不伪称任务完成；其自动提交与取消子代理政策须单独适配 |
| [Worktree cleanup：工作副本清理][cleanup] | 先只读清点占用和工作价值，给出清理建议 | 删除是明确决策门；不能靠“清理”掩盖未提交工作 |

## 6. 理解与设计：让后续动作有依据

### 6.1 代码怎样运行，与当初为何这么写，是两种问题

`how` 要追踪入口、组件、数据与控制流、边界、实际读过的文件和未知。只列文件名不算理解。[理解技能][how]、[探索者说明][how-explorer]

`why` 从具体代码、符号、提交和关联讨论开始，按可访问来源调查。结论分为直接证据、相互支持、推断、猜测与未知；反对替现状编一个合理故事。没有查询到的原因、未接入的来源，都要说明。[原因调查][why]、[证据分级][epistemics]

**适配建议：** 分析 PStack 或 x-rail 时，应分别回答“规则现在做什么”“设计上想避免什么”“实际运行是否有效”。前两者有文字或代码依据，不代表第三者已经成立；历史动机缺资料就保留未知。

### 6.2 架构选择先比较结构，再写实施清单

架构技能先理解，再以 `arena` 比较至少两个结构不同的设计。像同一页面分别尝试路由驱动和本地状态驱动，候选应有不同组织方式，而非同一方案换几处命名。设计从调用者如何使用开始，推导类型、签名和所有权。[架构][architect]、[设计说明模板][rationale]

`arena` 的流程是同题多解、独立评判、选一个基础，再吸收少量有价值的部分。候选明显分歧可能说明任务没有定义清楚，应重写问题；不能平均混合。综合后的产物要重新验证。[候选比较][arena]

原文的设计危险信号包括：浅包装、泄露内部信息、按处理时间先后拆模块、透传函数、所有权分散、一个任务两套路径、可随意导入内部实现、手工同步的清单。[设计危险信号][red-flags]

**适配建议：** 简单明确改动可以直接做；重大结构选择才付出候选成本。若不采用上游固定多模型探索，仍需用现有模式、原型或可对比结构解释为何选择可靠。额外代理调用必须沿用本会话授权。

### 6.3 实施偏离是反馈，不是总能靠例外消化

架构草图是实施约定。新增参数、共享锁、转换绕过等偏离需要分析：原设计漏条件、需求变化，还是实现越界？同类偏离反复出现时，回到理解和设计；不要让每个调用方知道越来越多内部规则。[实施与重设计][architect-scrap]

这条原则也适用于工作流：如果“保护现场”“少打扰”“减少上下文”等要求只能靠反复追加特例维持，应检查职责和信息来源，而非继续补提醒。此句是本文对 x-rail 的适配建议。

## 7. 分工与上下文：为什么委派不等于并行

### 7.1 四个不同目的

**阅读归纳：** PStack 的代理使用至少服务四种目的：承接执行材料、分离实现与判断、比较不同方案、覆盖独立场景。只有其中一部分直接缩短等待。

| 目的 | 原文机制 | 不能混用的地方 |
| --- | --- | --- |
| 理解跨系统事实 | `how` 多角度探索后综合；`why` 按来源调查 | 不能把多个探索结果当多份独立验证 |
| 比较整体方案 | `arena` 同题候选、选基础并吸收 | 不等于不同人各做一块后拼接 |
| 覆盖或竞赛 | `swarm` 声明分片或竞争规则再派发 | 覆盖要求每个必需分片有结果；竞赛可按事先规则选取 |
| 设计、实现、判断分工 | 功能流程委派实现，交付流程独立核验 | 有顺序依赖也能隔离执行材料；独立判断不能由实现者自报代替 |

来源：[理解][how]、[候选比较][arena]、[覆盖与竞赛][swarm]、[功能][feature]、[交付][shipping]。

### 7.2 拆分先看共享约定和真实所有权

功能流程要求列四项：阻塞前置、独立工作、共享可变状态、最小安全拆分。代码紧密耦合的一项功能先由一位负责人承接；父层并行适合独立产物。阶段变化后重新检查。[功能][feature]

共享对象不限代码文件，还包括分支、数据库、构建产物、缓存、模拟器和服务进程。PStack 的原则先问能否分别持有独立对象，再考虑锁。例子是两位执行者各写自己的结果文件，汇总时再读取，而非同时改一个总状态文件。[共享状态][p-separate-before-serializing-shared-state]

### 7.3 任务说明是交接产品

大型协调流程要求说明目标、允许和禁止路径、必要上下文、逐条验收、准确验证动作、时间边界、返回内容及持续约束。填不出必要内容说明工作尚未定义清楚。依赖是资料传递，不能只告诉后继“等前项完成”。说明大小按实际工作缩减。[任务说明][orchestrate-brief]

这里有明确的来源边界：上游模板含运行时间上限；本项目用户要求不主动给子代理设置总时限，故不能照搬该字段。目标、范围、证据与返回责任仍须保留。

### 7.4 新工作、续接与真实性

入口倾向给新工作干净执行者，并合并原任务说明、后续指示和上次结果；只有状态难以搬移时才续接原代理。[代理规则][subagents]

原文大型协调说明又要求每次派发和恢复传递持续约束，本地可给文件路径，云端要给确实可访问的材料。摘要丢掉限制会使错误在下游放大。[任务说明][orchestrate-brief]

**适配建议：** x-rail 必须遵守当前宿主的原运行查询与续接协议，不能照搬“修复一律新开”或任意换模型。共同目的应保留：新工作不无谓继承整个历史；续接不丢约束；实际副本与环境可核对。新代理标识本身不能证明上下文干净。

## 8. 验证与交付：检查对象、证据版本和结束条件

### 8.1 按真实使用入口证明结果

缺陷流程明确：在对应入口自己复现，不能在能操作的情况下把复现推回用户；运行证据确认原因后再设计修复，并在原入口复验。本地便宜测试用于固定分支行为，不能独自证明真实缺陷已消失。[缺陷修复][bugfix]、[测试驱动修复][tdd]

如前端组件测试能证明状态切换，但无法单独证明线上用户具备权限、入口可达且请求成功。最终需要什么证据由实际承诺决定。PStack 的项目验证技能把功能入口、前置数据、可操作步骤、观察值和陷阱组织成可维护地图，并要求验证生成的验证技能确实可用。[生成验证技能][create-verify]、[维护验证技能][maintain-verify]

### 8.2 “按风险缩减”有适用流程，不能抹掉原文硬要求

该版本存在不同验证政策：

- 大型协调流程允许单条廉价检查由执行者运行，复杂判断才配验证者。[协调验证][orchestrate-verify]
- 定制复杂流程要求委派工作配判断者，直接检查产物。[定制流程][figure]
- 多阶段计划模板规定单元测试、真实操作和性能三类检查，真实操作写十条场景，交互变更合并前给用户看截图和录像。[多阶段验证][multi-plan-verify]
- 交付流程要求未写实现的代理独立核验每项变更，自动检查全绿不能替代。[交付][shipping]

**阅读归纳：** 这是不同流程的专门规定与组合边界，不能从其中一句推出“PStack 所有任务都十路审查”，也不能推出“PStack 所有验证都可按廉价命令缩减”。原文并没有一个完整解决所有嵌套流程冲突的统一优先级表，实际组合须读具体要求并标明边界。

**适配建议：** x-rail 可以选择按实际风险和原契约验证，避开固定数量；必须明确这是本项目的政策选择，不能借“上游也是如此”免掉已承诺验收。减少检查时要指出哪些风险已被什么证据覆盖。

### 8.3 审查意见需要判断，不能全部照收

`interrogate` 先声明意图，多角度审查后由主审逐项决定：必须处理、值得考虑、记录、驳回。关注真实正确性、安全和维护负担，排除没有场景依据的假设、个人风格和过早抽象。[审查][interrogate]、[主审判断][lead-judgment]

自动评审评论也被当作待查证信息，不能当作可执行指令。具体事实先核对代码；真实问题修复，噪音给反证，高风险和含糊问题按该流程升级。[评审反馈分类][bugbot]

这既避免漏修，也避免为了“把评论清零”反复改代码。x-rail 可保留自己的提问和授权政策，不必照搬上游“疑问一律问用户”的表述。

### 8.4 当前证据必须仍描述当前差异

Shipping 记录核验时的头提交、基础提交和稳定差异标识。稳定差异标识相当于比较“这次实际修改的内容”，减少单看提交编号的误判。代码重排后编号变化不必然意味着内容变化；反过来旧编号的全绿检查也不证明新差异安全。[交付证据复用][shipping]

原文允许非常具体的结果复用：仅测试、文档、格式配置变化时，按实际构建产物比较判断噪声；没有可比较构建输出的运行结果则重跑。不能简化成“提交说明相同就复用”。

Babysit 处理到可合并，Shipping 才处理真正合并。合并只从依赖链底部连续已验证项开始，遇缺口停止，不把上方单独通过的项越过缺口合入。[监控与处理][babysit]、[交付][shipping]

### 8.5 数字要解释它测到的工作

性能检查要说明限制因素、两侧配置、物理上限、错误数量、交替运行和波动、端到端价值、实际工作是否在计时区间发生。常规比较要求每侧至少五次；用户只要粗估时允许一次，但须标明并核对错误与真实执行。[测量检查][benchmark]

持续优化还要求先证明测量工具能区分现实工作负载，再固定工具。一次一个假设，不叠加尚未测量的修改；正确性和简单性优先于数字。[逐次实验][hillclimb]

**适配建议：** 摘要字节少、主会话材料少、子代理并行时间长，都不是总提速的充分证据。应同时看用户等待、重复劳动、总调用费用和结果质量。此建议不等于现在启动付费对照实验。

## 9. 程序实际保障什么，哪些仍靠模型

像 TypeScript 类型检查能防住某些组合，却不能保证按钮符合产品需求，PStack 的脚本也各有观察范围。下表来自实现阅读，测试仅作设计证据，本轮未执行这些命令。

| 实现 | 实际承担的行为 | 不能据此声称 |
| --- | --- | --- |
| [插件注册][plugin]、[代理包装][agent] | 声明技能与代理入口；执行代理读取同一主入口 | 已自动加载所有规则，或模型每次正确分流 |
| [计划检查 `check-plan.mjs`][check-plan] | 检查章节、顺序、验证声明、十条场景编号、截图路径、通过描述及性能块等结构 | 场景有业务价值、截图真实、已运行，或任务拆分合理 |
| [记录命令 `orch.ts`][orch-cli] | 调用状态存储，输出简短或完整数据；处理参数与错误 | 自动派发、等待或唤醒代理；原流程明确这些由宿主和模型负责 |
| [记录存储 `store.ts`][store] | 表格与结构数据解析、写入锁、临时文件改名写入、失活进程锁恢复、生成汇总 | 状态一定真实，记录包含完整业务验收，或所有多步文件动作都无故障风险 |
| [工作项状态更新][store-state] | 要求状态非空，按工作项更新文本和相关标识 | 存在与 x-rail 等同的工作项生命周期完成门；该字段并未在此限定为完整状态枚举 |
| [验证账本登记与查询][store-ledger] | 校验判定类别，按变更申请及提交标识保存或返回一行；同一键的新登记替换原行 | 查询成功即通过；查询也可返回验证失败、受阻或仅类型检查。程序不自行核对证据文件真实性，也不检查登记者是否独立 |
| [GitHub 状态读取][watch-github]、[判断逻辑][watch-policy] | 读取并归类冲突、评审线程、检查、草稿与关闭状态；支持状态查询、持续观察和队列推进 | 产品行为通过、授权合并或适用于所有代码托管平台 |
| [观察器类型模型][watch-types]、[编译期反例][watch-type-tests] | 将“就绪”等结果与所需证明关联，限制某些矛盾组合 | 外部服务真实正确，或所有运行异常已覆盖 |
| [依赖准备][bootstrap] | 按依赖清单与锁文件指纹判断是否需要安装命令依赖，安装后重启命令 | 无副作用的纯只读操作；执行前应知道它可能安装依赖 |
| [工作副本审计][worktree-audit] | 汇总工作副本大小、合并与修改状态，提出分类 | 已清理；脚本本身不执行删除 |
| [决定日志脚本][log-script] | 补时间和表头，清理表格分隔字符、防止单元格被当公式 | 日志内容属实、证据链接有效或决定合理 |

几个容易过度解释的实现细节：

1. 新提交标识在账本中查不到旧键，因此需要当前版本证据；旧行并非自动从历史删除。[账本查询][store-ledger]
2. 判定类别是受限的，工作项状态文本却更宽松。不同字段不能笼统说成“全都强类型保障”。[状态][store-state]、[账本][store-ledger]
3. 大型协调的分支前沿发现依赖 Graphite（管理分支依赖栈的工具）；Babysit 与 Shipping 则优先 GitHub 命令或 Origin。不同流程的工具要求不能互相替代。[协调前沿实现][store-frontier]、[监控][babysit]、[交付][shipping]
4. 状态观察器的查询错误退避、流程的重试、宿主的模型请求超时，是不同层次。上游允许某类重试，不代表 x-rail 获得同样权限。[观察循环][watch-poll]、[协调故障处理][orchestrate-failure]
5. 多阶段计划会要求十条真实操作场景，检查脚本主要验证其结构和必需文本；结构检查通过不证明十条场景已经执行。[计划要求][multi-plan-verify]、[脚本][check-plan]

## 10. 长任务、恢复与反馈如何闭环

### 10.1 一个目标持续推进，与长期项目协调分开

持续执行先声明能被事实否定的结束条件，按事件唤醒或合适间隔观察，小步改动、核对、保留或撤销。旁支修复另行组织，再回到主目标；不能降低目标换取完成。[持续执行][autonomous]

大型协调才增加轨道、持续约束、工作单元、验证账本、通知收件箱和汇总状态。先代表单元，再滚动补位；已验证项持续进入集成，不等所有实现完才开始交付。[大型协调][orchestrate]

原文有具体经验参数，例如协调可处理的约十个在途子任务、约七成时间后收敛派发、单元时间上限。它们是该流程的组织策略，不是经本次实验验证的普遍常数，也不是复杂度分类公式。

### 10.2 通知不应抢占关键判断

大型协调将完成通知视为待处理事件。正在写任务说明、处理冲突决定或写状态时，先完成安全片段，再批量整理结果；深度检查另设工作，不在整理通知时临时展开。到达结果要核对，遗漏的执行者必须有结局。[通知处理][orchestrate-drain]

**阅读归纳：** 目标是在及时消费结果与避免主会话频繁切换之间取平衡。x-rail 可以复用现有通知与原生完成事件，不必引入第二个收件箱；但不能把“避免打断”解释成等待全部结束。

### 10.3 恢复保存的是事实和第一步

接续流程读取先前轨迹与真实分支现场，比较完成和待办，明确接续点，避免从零重做；继承结论仍要对照原目标核对真实产物。[接续][pickup]

安全暂停明确只在暂停请求下使用，保存意图、已验证结果、现场、下一步和陷阱。[暂停][pause]包含自动工作中提交及取消子代理等动作，这些属于上游具体政策，x-rail 不应因“持久化”原则自动获得相同授权。

恢复时还要区分：执行者真死了、模型请求失败、外部服务慢、任务没进展。大型协调要求只读查询存活状态，不能用“恢复”来探活；迟到产物要对照当前现场再接受。[故障与存活][orchestrate-failure]

### 10.4 重复错误先检查能否从结构消除

`correct` 将重复错误分成类别，先改架构，再用类型或明确报错的检查，再测试行为，最后为必须判断的部分写文档。新增检查要能在真实旧错误上失败，才能证明它会拦截该类错误。[纠错技能][correct]

`reflect` 从当前实际会话提炼教训，判断、工具和发散视角分别审阅后综合。适合程序保障的项目转为实现待办，不冒充多写一条文字就解决。原流程对全局技能修改保留明确批准门。[反思技能][reflect]

`show-me-your-work` 保存决定、原因、证据和结果，记录关键转向而非每次读文件。交付前对照实际会话审计，错误行追加更正，不改写历史；原文还要求不同模型家族审查轨迹。[决定记录][trail]

`eval` 检验规则是否改变行为：执行者看到自然任务，考核点与模型身份隔离，最终按实际读取、操作与产物评判。执行者说“我遵守了”不是证据。[行为评估][eval]

### 10.5 自动化扩展仍需身份、输入和动作边界

Benny 是本包里的可选问题报告自动化：先读取完整报告并分类，再由可信身份和固定消息位置给出标记，复现链路只处理符合条件的缺陷或性能报告；有既存修复先验证，确认复现且范围可控才尝试修复。[自动化分流][benny-triage]、[复现与修复][benny-fix]

它要求配置、控制适配器和实际功能地图，拒绝把任意外部文本变成命令。建立自动化本身也有宿主能力与外部创建边界。[自动化设置][benny-setup]

**阅读归纳：** 这是“观察到什么、信任谁、何时允许下一动作”的组合示例。它依赖外部系统，不是下载插件后自动运行的常驻服务，本轮未连接任何外部自动化。

## 11. 遇到问题时从哪里查

| 当前问题 | 优先回查 | 先确认的事实 | 避免的直接反应 |
| --- | --- | --- | --- |
| 用户不断提醒同一种错 | 第 4.4、10.4 节；纠错与结构化教训 | 是单例还是重复类别；已有规则由什么保障 | 再加一条同义提醒 |
| 主会话越来越重 | 第 7 节；上下文、阅读负担、分工 | 哪些材料被读入、为什么回流，职责和资料能否隔离 | 只缩短最终报告，或只调压缩阈值 |
| 任务越做越复杂 | 第 3.3、6.3 节 | 哪个新事实否定了原边界；同类偏离是否反复 | 重贴“大任务”标签但不改组织方式 |
| 代理很多，总体反而慢 | 第 7、10.2 节；工具杠杆 | 独立性、交接量、共享环境、通知处理和集成等待 | 继续加代理，或一律禁委派 |
| 串行工作都由主会话亲自完成 | 第 3.2、7.1 节 | 是否有完整、可交接的执行段；目的是否包含材料隔离 | 把“不能并行”当成“不能委派” |
| 检查全绿但结果不好用 | 第 8.1、9 节 | 当前检查观察了哪一层，真实用户入口是否验证 | 再跑同一批无关检查 |
| 审查越加越多 | 第 8.2、8.3 节 | 所属流程和既有契约；剩余真实风险；意见是否成立 | 照收所有建议，或未经依据取消必需审查 |
| 方案反复补例外 | 第 4.1、6.3 节 | 是否错误前提、重复所有权、内部规则泄漏 | 再加抽象层和条件 |
| 状态文件齐全却没有进展 | 第 2、9、10.1 节 | 真实产物、下一动作、是否解决未知 | 把更新时间和记录数量算成果 |
| 宣称提速却体感没变 | 第 8.5 节 | 实际计时区间、错误数、工作量、总等待与总费用 | 从局部字节或单次运行推导普遍提升 |
| 接手后重做、漏约束 | 第 7.3、7.4、10.3 节 | 实际输入、原运行、允许范围、有效证据和第一动作 | 从头研究或无条件接受旧总结 |
| 规则多却总被漏读 | 第 2、4.2、10.4 节 | 触发入口、重复内容、冲突、能否由程序保障 | 强制每轮读完整规则库 |

这张表是维护时的定位索引，不是每项任务必填的检查表。

## 12. 怎样用这份参考调整 x-rail

### 12.1 区分共同原则、项目政策和宿主能力

| 层次 | 应保留或确认什么 | x-rail 适配边界 |
| --- | --- | --- |
| 通用原则 | 先理解、可验证结果、结构承载规则、减少重复、隔离写入、有效证据、及时纠偏 | 改编具体形式时，说明原目的由什么承担 |
| 项目政策 | 中文、先读后改、保留用户修改、普通任务轻量、严格记录、四类敏感决定 | 以当前用户要求为准，不因上游宽授权而放松 |
| 宿主能力 | 实际代理协议、续接资格、通知、文件可访问性、模型可用性和真实上下文信号 | 使用本宿主能力，不模拟存在但实际不可用的唤醒、隔离或恢复 |
| 上游经验策略 | 默认模型、云端优先、固定评估规模、日志位置、时间参数和交付工具 | 只在需求、授权、成本和证据支持时采用，不能冒充通用原理 |

例如，采用“简单任务直接做”可以符合用户习惯；同时仍要处理实现与判断混杂、主会话材料拥挤的问题。采用 x-rail 的统一任务记录位置也可以；但共同文件边界应由清楚的权威位置维护，避免每个短原则重复整套生命周期。以上是适配建议，不是本轮修改。

### 12.2 每次改进留下能检查的因果关系

不要求新建表格。可在既有方案或决定中用一段话说明：

1. **现状／问题／影响**：哪次可追溯行为出了问题，对结果或协作造成什么损失。
2. **原则依据**：原文要求是什么，适用流程和前提是什么；未知和推断分别标明。
3. **当前缺口**：入口没触发、职责不对、资料拿不到、规则冲突、工具缺保障，还是模型这次偏离。
4. **最小措施**：先考虑移除冗余、集中事实、调整所有权或程序检查；仍需判断的才写短规则和反例。
5. **反例验证**：至少观察一个本应改变行为的场景，以及一个不该增加负担的简单场景。根据实际变化选择足够的检查，不要求固定新增模型调用。
6. **结论与推翻条件**：文字、脚本、真实行为和效率分别报告；新措施如果增加更多负担或不能改变问题，应重新选择。

例如，“改按钮后才发现权限联动”应观察执行者何时发现新事实、何时停止扩大改动、如何调整范围与验证。“十份文件同步一句话”用于核对不会仅因文件多升级为重流程。考核过程不要提前泄露期待动作，否则只能证明执行者会复述提示。

### 12.3 文档本身也要控制负担

**已按推荐选了“跨版本设计参考”，因为它能保留原理和出处，同时让每个版本方案只写本次选择。** 本文放在 `docs/`，不绑定 0.0.6，也不整篇复制进技能。

- 原理和原文索引在本文维护；实施状态留在原任务记录，版本取舍写对应方案的 `DECISIONS.md`（决策记录）。
- 仅修改或调整 x-rail 本身时按需读取相关部分；日常使用 x-rail 相关技能时不读取，不加入技能执行流程、前置阅读或自动加载清单。
- 发现偏差先回到原文确认，再修正参考；不能让本文成为替代源码的永远正确结论。
- 新政策如果与本文不同，说明差异和替代措施即可；不为“像 PStack”牺牲实际使用需要。

## 13. 来源覆盖、可复核基线与限制

### 13.1 本次阅读范围

本次对本地副本的说明、技能、流程、参考材料、脚本与测试进行了分组读取和索引；核心入口、24 条原则、关键流程与判定实现另做逐段核对。大型测试和外部资料适配说明用于核对职责与保障范围，未逐行作全包缺陷审计。

| 材料 | 覆盖与用途 |
| --- | --- |
| 插件元信息、README、10 篇使用导读及其目录 | 版本、装配、能力关系与使用边界 |
| 顶层 51 个技能入口，其中 24 个原则 | 原则全表、理解／设计／执行／验证／反馈关系 |
| 23 份任务流程 | 常规任务、复杂任务、交付、恢复和结束条件 |
| 两份代理说明与专项参考文件 | 角色包装、调查输出、设计危险信号、审查、证据分级、反馈 |
| 协调记录、GitHub 状态观察、计划检查、依赖准备、工作副本审计和日志脚本 | 核对文字要求与实际程序保障的差异 |
| 协调与观察器测试、编译期反例 | 核对作者设计的正反例及边界；本轮未运行 |
| Benny 自动化配置、流程与适配示例 | 信任、分流、复现、既有修复验证与外部动作边界 |
| 辅助写作、类型实践、接入和用户定制说明 | 阅读负担、配置和按需组合，不等于本轮执行它们 |

图片、许可文本和依赖锁内容不作为流程判断依据；外部宿主内建技能与连接服务没有在此源码副本中完整提供，不能称为已读其实现。

### 13.2 内容指纹

版本来自[插件元信息][plugin]，声明为 `0.15.15`。该副本无 Git 提交信息，不能复原完整上游变更历史。

SHA-256（Secure Hash Algorithm 256-bit，256 位安全散列算法）可理解为文件内容指纹。以下是本次读取集合的综合指纹，便于识别来源变化：

```text
文本集合：153 个文件
扩展名：.md .ts .json .sh .yaml .mjs .tsv
综合 SHA-256：dac40e3eae6debe0a0874aad2332196ed5c3ba1aec35eb9330417b27c48c3b6e
算法：按相对路径排序；每项为 相对路径 + NUL + 文件原字节SHA-256十六进制 + 换行；对拼接后的UTF-8字节计算SHA-256。
```

这里 NUL 表示值为零的分隔字节，UTF-8 表示文本编码。综合指纹能确认集合是否相同，不能从指纹还原源码；需要长期复现时应保存合法的版本化来源副本或补上可核实的上游提交。本轮没有复制整套 PStack，也没有虚构上游提交。

下方引用使用本地绝对路径，便于当前环境直接回查；相对来源路径均可从链接看出。分享或移动仓库时，需要恢复来源目录或将引用转换为已核实提交的公开链接。官方仓库入口为 <https://github.com/cursor/plugins/tree/main/pstack>，其中 `main` 会变化，不能当成本次固定版本的永久依据。

### 13.3 本文不能证明的事

本文能够支持原规则和关键实现边界的解释。真实模型服从率、普遍正确分流、实际提速、总费用、外部服务行为及长期效果，仍需相应运行证据。

维护时优先复查会影响结论的来源：入口分流、Feature 的拆分与委派、具体流程验证要求、Orchestrate 的任务说明与试跑、Shipping 的证据复用、Correct／Reflect／Eval 的反馈方法，以及相关脚本。来源变了就更新受影响解释，不无条件重做所有研究。

[entry]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/SKILL.md:14
[principles]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/SKILL.md:38
[routing]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/SKILL.md:119
[subagents]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/SKILL.md:91
[plugin]: /Users/yuanxj/Downloads/plugins-main/pstack/.cursor-plugin/plugin.json:1
[external]: /Users/yuanxj/Downloads/plugins-main/pstack/README.md:231
[agent]: /Users/yuanxj/Downloads/plugins-main/pstack/agents/poteto-agent.md:1
[comment-agent]: /Users/yuanxj/Downloads/plugins-main/pstack/agents/comment-sicko.md:1
[how]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/how/SKILL.md:7
[how-explorer]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/how/references/explorer-prompt.md:1
[why]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/why/SKILL.md:7
[epistemics]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/why/references/epistemics.md:1
[architect]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/architect/SKILL.md:7
[architect-agree]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/architect/SKILL.md:43
[architect-scrap]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/architect/SKILL.md:53
[rationale]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/architect/references/rationale-template.md:1
[red-flags]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/architect/references/design-red-flags.md:1
[arena]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/arena/SKILL.md:7
[swarm]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/swarm/SKILL.md:7
[figure]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/figure-it-out/SKILL.md:15
[interrogate]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/interrogate/SKILL.md:7
[lead-judgment]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/interrogate/references/lead-judgment.md:1
[tdd]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/tdd/SKILL.md:7
[benchmark]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/benchmark-checklist/SKILL.md:7
[create-verify]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/create-verification-skill/SKILL.md:7
[maintain-verify]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/maintain-verification-skill/SKILL.md:7
[correct]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/correct/SKILL.md:7
[reflect]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/reflect/SKILL.md:7
[trail]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/show-me-your-work/SKILL.md:7
[bugbot]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/references/bugbot-triage.md:1
[investigation]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/investigation.md:1
[bugfix]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/bug-fix.md:1
[feature]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/feature.md:1
[refactor]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/refactoring.md:1
[perf]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/perf-issue.md:1
[hillclimb]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/hillclimb.md:1
[runtime]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/runtime-forensics.md:1
[trace]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/trace-forensics.md:1
[prototype]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/prototype.md:1
[visual]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/visual-parity.md:1
[author]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/authoring-a-skill.md:1
[eval]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/eval.md:1
[multi-plan]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md:1
[multi-plan-verify]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md:13
[autonomous]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/autonomous-run.md:1
[orchestrate]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:1
[orchestrate-brief]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:34
[orchestrate-pilot]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:60
[orchestrate-drain]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:68
[orchestrate-verify]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:85
[orchestrate-failure]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/orchestrate.md:93
[autopilot-full]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/autopilot-full.md:1
[autopilot-stack]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/autopilot-stack.md:1
[babysit]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/babysit.md:1
[shipping]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/shipping.md:1
[opening]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/opening-a-pr.md:1
[pickup]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/session-pickup.md:1
[pause]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/pause-safely.md:1
[cleanup]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/playbooks/worktree-cleanup.md:1
[check-plan]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/check-plan.mjs:5
[orch-cli]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/orch/orch.ts:254
[store]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/orch/store.ts:324
[store-state]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/orch/store.ts:1267
[store-ledger]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/orch/store.ts:1331
[store-frontier]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/orch/store.ts:1005
[watch-github]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/watch-pr/github.ts:235
[watch-policy]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/watch-pr/policy.ts:144
[watch-poll]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/watch-pr/policy.ts:361
[watch-types]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/watch-pr/types.ts:1
[watch-type-tests]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/watch-pr/types.compile.ts:1
[bootstrap]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/bootstrap.ts:1
[worktree-audit]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/scripts/worktree-audit.sh:1
[log-script]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/show-me-your-work/scripts/log.sh:1
[benny-triage]: /Users/yuanxj/Downloads/plugins-main/pstack/automations/benny/skills/triage-issue-reports/SKILL.md:7
[benny-fix]: /Users/yuanxj/Downloads/plugins-main/pstack/automations/benny/skills/reproduce-and-fix-issues/SKILL.md:7
[benny-setup]: /Users/yuanxj/Downloads/plugins-main/pstack/automations/benny/skills/setup-benny/SKILL.md:7
[p-attack-the-premise]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-attack-the-premise/SKILL.md:7
[p-boundary-discipline]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-boundary-discipline/SKILL.md:7
[p-build-the-lever]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-build-the-lever/SKILL.md:7
[p-encode-lessons-in-structure]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-encode-lessons-in-structure/SKILL.md:7
[p-exhaust-the-design-space]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-exhaust-the-design-space/SKILL.md:7
[p-experience-first]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-experience-first/SKILL.md:7
[p-explain-the-number]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-explain-the-number/SKILL.md:7
[p-fix-root-causes]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-fix-root-causes/SKILL.md:7
[p-foundational-thinking]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-foundational-thinking/SKILL.md:7
[p-guard-the-context-window]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-guard-the-context-window/SKILL.md:7
[p-laziness-protocol]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-laziness-protocol/SKILL.md:7
[p-make-operations-idempotent]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-make-operations-idempotent/SKILL.md:7
[p-migrate-callers-then-delete-legacy-apis]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md:7
[p-minimize-reader-load]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-minimize-reader-load/SKILL.md:7
[p-model-the-domain]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-model-the-domain/SKILL.md:7
[p-never-block-on-the-human]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-never-block-on-the-human/SKILL.md:7
[p-outcome-oriented-execution]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-outcome-oriented-execution/SKILL.md:7
[p-prove-it-works]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-prove-it-works/SKILL.md:7
[p-redesign-from-first-principles]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-redesign-from-first-principles/SKILL.md:7
[p-separate-before-serializing-shared-state]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md:7
[p-sequence-verifiable-units]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-sequence-verifiable-units/SKILL.md:7
[p-subtract-before-you-add]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-subtract-before-you-add/SKILL.md:7
[p-test-behavior-not-implementation]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-test-behavior-not-implementation/SKILL.md:7
[p-type-system-discipline]: /Users/yuanxj/Downloads/plugins-main/pstack/skills/principle-type-system-discipline/SKILL.md:7

## 本地实现映射（2026-10-17）

| 来源 | 本地适配 | 验证边界 |
| --- | --- | --- |
| poteto-mode/SKILL.md | 十路交付分流、默认完整单元交接、宿主恢复约束 | XML 与入口检查，非模型服从证明 |
| figure-it-out/SKILL.md | 复杂定制流程、验证先行、代表单元、逐项与整体核验 | 本地 CLI 演练 |
| poteto-mode/playbooks/autonomous-run.md | 可检查完成谓词、持续推进与按证据转向 | finish 拒绝半成品，未做真实持续模型实验 |
| poteto-mode/playbooks/orchestrate.md | frontier、滚动补位、notify/inbox/consume、失败分类、版本绑定、冷启动 | Python 标准库持久化事实；Pi 执行模型动作；不复制云端/Cursor/Graphite |

详细当前规格见 `plans/refactor-2026-10/pstack-local-implementation-plan.md`；公开接口与恢复见 `skills/x-rail/modules/orchestration.md`。脚本复用 contract/state/evidence；不将 pstack 的 units.tsv 复制成第二状态库。
