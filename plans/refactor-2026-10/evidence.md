# x-rail 重构取证报告

**日期**: 2026-10-17  
**分支**: v3 (worktree)  
**工作区**: 干净，无未提交修改

---

## 一、当前项目现状

### 1.1 入口文件规模

| 文件 | 大小 | 行数 |
|------|------|------|
| `skills/x-rail/SKILL.md` | 25,012 字节 (约 25 KB) | 126 |
| `skills/x-rail-long/SKILL.md` | 3,663 字节 (约 3.6 KB) | - |
| `skills/x-rail/scripts/task.py` | 30,291 字节 (约 30 KB) | 558 |

**证据来源**: `wc -c`, `wc -l`

**问题确认**:
- ✅ x-rail/SKILL.md 确实约 25 KB，超过目标 5 KB 约 5 倍
- ✅ task.py 约 30 KB，功能集中在单文件，包含 17 个函数

### 1.2 核心结构

**入口技能** (`skills/x-rail/SKILL.md`):
- 定义了 `<routing>` 表：10 个路由（investigate/research/design/plan/exec/bugfix/review/ops/mixed/fast-answer）
- 每个路由引用外部 playbook 文件（`playbooks/<name>.md`）
- 按需加载参考技能（如 `x-how`、`x-typescript-best-practices`）
- 包含完整的 workflow、cost_policy、task_directory、verification、recovery 等章节
- 所有技能设置 `disable-model-invocation: true`，不会被模型自动唤起

**任务脚本** (`scripts/task.py`):
- 主要命令：`start`, `finish`, `update`, `capture`, `record`, `summary`, `run_verification`, `complete`
- 管理 `.work-docs/tasks/<task-id>/` 目录结构
- 执行严格的契约校验和状态管理
- 使用管道记录格式（pipe record）

### 1.3 近14天提交分析

**总提交数**: 40 次  
**修复类提交**: 8 次 (20%)

**关键词分布**:
- 门禁/验证相关: 9 次
- 修复相关: 7 次
- 契约/schema: 4 次
- 清理: 1 次
- 子代理: 1 次
- 恢复: 1 次

**典型修复案例**:
1. `2865386`: 门禁旧名护栏由点状枚举改为通配
2. `10d9637`: 修复 check-workflow 在软链安装下的静默空转
3. `2294466`: 修正改名后的失效指针并加固旧名回归护栏
4. `b196efe`: 拒绝宿主加载器会丢弃的技能头
5. `9661563`: 接受任意证据文件扩展名

**模式识别**:
- 门禁和检查器相关问题频繁出现（9次）
- 多次修复"旧名"、"指针失效"、"护栏"问题 → 暗示重构或重命名后的回归
- 检查器在特定环境（软链安装）下失效
- 契约和 schema 相关修改较多（4次）

### 1.4 真实会话取证

**限制**: 无法直接访问 Pi Agent 的会话日志或错误日志。

用户提到的 "434 次工具错误" 无法直接验证来源和分类。需要：
- 确认日志路径（Pi Agent 配置目录）
- 确认错误分类方式
- 确认统计周期

**结论**: 无法取证真实会话错误 → 记录为"无法验证"

---

## 二、已知问题验证

### 2.1 ✅ 规则文件过度集中

**现状**: 
- `skills/x-rail/SKILL.md`: 25 KB
- 包含：authority、routing、workflow、cost_policy、task_directory、execution、work_items、lifecycle、decision_policy、verification、recovery、output_contract
- 单个严格任务可能加载：入口 25KB + playbook + 参考技能 + task.py 30KB ≈ 65KB+

**证据**: 文件大小测量

**根因**: 
- 历史上所有规则、策略、恢复机制都写在入口 SKILL.md
- 没有按需加载机制（routing 表引用 playbook，但入口本身仍包含所有章节）

**影响**: 
- 弱模型（如 DeepSeek v4.1 Flash）难以在 65KB+ 规则中准确服从所有细节
- 上下文压缩后，关键规则可能丢失

**是否值得修复**: ✅ **是**，这是核心问题

**最小有效改法**:
1. 入口 SKILL.md 只保留：目的、路由表、最小安全规则、恢复入口
2. 详细规则拆分到按需加载的模块（如 `modules/verification.md`、`modules/recovery.md`）
3. Playbook 保持现状（已经是按路由分离）

**不改的后果**: 
- 弱模型继续高错误率
- 上下文压缩后规则丢失
- 新增规则会进一步膨胀文件

### 2.2 ⚠️ 缺少 pstack 能力

**pstack 核心能力**（从索引中提取）:

| 能力 | pstack 实现 | x-rail 现状 | 评估 |
|------|-------------|-------------|------|
| **TDD** | `/tdd` 技能，test-first 修复 bug | `playbooks/exec.md` 提到"非平凡行为默认先写失败测试" | 部分存在，但不强制 |
| **recall** | `/recall` 技能，从聊天历史和共享记录重建上下文 | 依赖 `state.md` + `checkpoint` | 有类似机制，但不智能 |
| **reflect** | `/reflect` 技能，任务完成后捕获为技能编辑 | 无 | 缺失 |
| **never-block-on-the-human** | 原则技能，可逆操作直接执行 | `authority` 中"调用 x-rail 即授权...默认主动委派" | **已有** |
| **make-operations-idempotent** | 原则技能，操作可重复执行 | `recovery` 中"相关输入...变化时只重跑受影响检查" | 部分存在 |
| **sequence-verifiable-units** | 原则技能，每步可验证再进下一步 | `work_items` + `verification` | **已有** |

**结论**: 
- x-rail **已有** `never-block-on-the-human`、`sequence-verifiable-units` 的等效机制
- TDD 部分存在但不强制
- recall 机制较原始（文件读取 vs 智能摘要）
- reflect 完全缺失

**是否值得全部引入**: ⚠️ **部分引入**
- TDD: 值得强化（改为默认行为）
- recall: 当前机制够用，智能摘要可选
- reflect: 优先级较低（meta 能力）

### 2.3 ✅ 管道记录格式复杂

**现状**: 
- task.py 使用严格的 pipe record 格式
- 包含 contract.md、state.md、evidence/、handoff.md 等多个文件
- 模型需要准确调用 `task.py start|update|capture|record|finish`
- 记录格式有版本（`work_items_schema: 1`、`evidence_schema: 2`）

**证据**: task.py 源码、SKILL.md 中的 verification 章节

**根因**: 
- 为了支持严格验证和恢复，引入了复杂的状态机和记录格式
- 模型需要记忆参数、格式、调用顺序

**影响**: 
- 弱模型容易写错参数、遗漏字段
- 近14天有4次契约/schema相关修复

**是否值得修复**: ✅ **是**，但需权衡

**最小有效改法**:
- 方案A（激进）：替换为简洁 Markdown checklist + 可选检查器
- 方案B（渐进）：保留当前机制，简化参数和字段，改进错误提示

**推荐**: 方案A（符合用户要求）

**不改的后果**: 
- 弱模型继续高错误率
- 记录格式成为任务完成的隐性门槛

### 2.4 ✅ 上下文压缩后规则丢失

**现状**: 
- x-rail 依赖 SKILL.md 中的详细规则
- 上下文压缩后，4B 模型生成的摘要可能丢失关键规则

**证据**: 
- SKILL.md 25 KB 全部在入口
- 用户提到"上下文压缩后规则可能丢失，特别是小模型生成摘要时"

**根因**: 
- 规则未拆分，压缩时要么全丢，要么全留
- 没有明确的"核心规则"和"详细规则"分层

**影响**: 
- 恢复后模型不知道关键约束（如 cost_policy、decision_policy）
- 可能执行不安全操作或跳过必需验证

**是否值得修复**: ✅ **是**

**最小有效改法**:
1. 核心规则（安全边界、恢复入口）留在入口
2. 详细规则按需加载
3. 压缩后恢复时，优先读取 `state.md` + 核心规则，按需加载详细模块

**不改的后果**: 
- 长任务或跨会话任务可靠性差
- 恢复后模型"失忆"

### 2.5 ⚠️ 工具调用错误统计

**用户提到**: "近期会话统计过约 434 次工具错误"

**无法验证**: 
- 没有访问 Pi Agent 日志
- 不清楚"工具错误"的定义（task.py 参数错误？API 超时？权限错误？）
- 不清楚统计周期和总调用次数（错误率未知）

**结论**: ⚠️ **无法取证**，需要：
1. 用户提供日志路径或错误分类
2. 明确"工具错误"的定义
3. 统计总调用次数以计算错误率

### 2.6 ⚠️ 第三方 API 不稳定

**用户提到**: "第三方 API 不稳定，当前系统可能缺少合理的超时、错误分类和有限重试"

**x-rail 现状**:
- `recovery` 章节提到"失败不原样重试"
- `recovery` 提到"基础设施错误暂停依赖，保存准确错误与运行引用"
- 没有明确的超时设置（task.py 没有 `timeout` 参数）
- 没有明确的重试策略（文档说"不原样重试"但没有说是否有条件重试）

**结论**: ⚠️ **部分缺失**
- 有"不盲目重试"的意识
- 缺少明确的超时配置
- 缺少错误分类（API瞬时错误 vs 代码逻辑错误）
- 缺少有限重试机制（如 API 429/503 重试1次）

**是否值得修复**: ✅ **是**

**最小有效改法**:
1. 为工作项设置硬超时（如 15 分钟）
2. 区分错误类型：API瞬时错误（可重试1次）vs 逻辑错误（不重试）
3. 记录重试次数和失败原因

**不改的后果**: 
- API 超时导致任务卡死
- 瞬时错误被当作永久失败
- 浪费用户时间（明明重试一次就能成功）

---

## 三、pstack 对比分析

### 3.1 pstack 核心设计理念

从索引中提取的关键原则：

| 原则 | pstack 实践 | x-rail 对标 | 差距 |
|------|-------------|-------------|------|
| **Guard the Context Window** | 子代理隔离大负载，主上下文只保留摘要 | 子代理机制存在但默认不启用 | x-rail 更保守 |
| **Never Block on the Human** | 可逆操作直接执行，完成后给用户选择 | 已实现（`delegation="explicit-only"` → 将改为默认主动委派） | **一致** |
| **Make Operations Idempotent** | 操作可重复执行，收敛到相同终态 | 部分实现（重跑受影响检查） | x-rail 较弱 |
| **Sequence Verifiable Units** | 每步验证再进下一步 | 已实现（work_items + verification） | **一致** |
| **Pause Safely** | 明确的 checkpoint 和 resume 机制 | 已实现（state.md + handoff.md） | **一致** |
| **TDD** | test-first 修复 bug | 部分实现（非平凡行为默认先写测试） | x-rail 不强制 |

**结论**: 
- x-rail 在核心原则上与 pstack **基本一致**
- 主要差距：
  1. 上下文管理不如 pstack（入口文件过大）
  2. TDD 不强制
  3. 缺少智能 recall（pstack 有专门的 `/recall` 技能）

### 3.2 pstack 的任务状态模型

**pstack 模式**（从 `pause-safely.md` 推断）:
- 状态持久化到文件（如 `/tmp/<slug>-resume.md`）
- Checkpoint 包含：intent、progress、current state、next steps、key files、gotchas
- Resume 时读取 checkpoint，不依赖聊天上下文
- 使用 `units.tsv` 跟踪多个并行单元

**x-rail 模式**:
- 状态持久化到 `.work-docs/tasks/<task-id>/state.md`
- 包含：task_id、status、next_action、blocked_by、work_items 状态
- Resume 时读取 contract + state + checkpoint
- 单任务模型（没有 pstack 的 `units.tsv` 并行单元跟踪）

**差距**:
- x-rail 更重（完整的 contract/state/evidence 目录结构）
- pstack 更轻（单个 markdown 文件 + 可选的 units.tsv）
- x-rail 更严格（强制验证和证据绑定）
- pstack 更灵活（pause/resume 可选）

**是否需要对齐**: ⚠️ **不完全对齐**
- x-rail 的严格验证是差异化特性，应保留
- 可借鉴 pstack 的轻量 checkpoint（简化版 state.md）

### 3.3 pstack 的子代理编排

**pstack 模式**（从 `orchestrate.md` 推断）:
- 中心协调器 + 多个并行子代理
- 使用 `units.tsv` 跟踪每个单元的状态
- 子代理失败后不自动重启，而是记录 postmortem
- 明确的 liveness 检查（不用 resume 检查状态）

**x-rail 模式**:
- 主会话 + 可选子代理
- 子代理规则在 `playbooks/exec.md` 和 `work_items` 章节
- **当前**: `delegation="explicit-only"`（只有用户明确要求才用子代理）
- **用户计划**: 改为默认主动委派（但保留单写入者约束）

**差距**:
- pstack 默认并行 + 中心协调
- x-rail 默认单会话（更简单但可能更慢）

**是否需要对齐**: ⚠️ **部分对齐**
- x-rail 应保持"默认单会话"（符合用户"默认关闭子代理"要求）
- 但允许用户明确启用并行（保留能力）
- 不需要 pstack 的完整编排机制（`units.tsv` 等）

---

## 四、本机 Skills 和 Packages 清单

**限制**: 无法直接扫描本机 Pi Agent 的全局 skills 和 packages（需要访问 `~/.pi/agent/skills/` 或类似目录）

**当前项目 skills 目录**:

```
skills/
├── x-rail/
├── x-rail-long/
├── x-how/
├── x-why/
├── x-blast-radius/
├── x-codebase-design/
├── x-architect/
├── x-arena/
├── x-prototype/
├── x-technical-writing/
├── x-unslop/
├── x-typescript-best-practices/
├── x-principle-boundary-discipline/
├── x-principle-fix-root-causes/
├── x-requesting-code-review/
├── x-receiving-code-review/
├── x-wizard/
└── x-create-verification-skill/
```

**证据来源**: `find skills -name 'SKILL.md'`（前面执行过）

**需要用户手动处理**:
1. 扫描 `~/.pi/agent/skills/` 或 Pi 配置目录
2. 识别与 x-rail 重叠的技能
3. 评估是否保留/禁用/替换

---

## 五、待验证项

以下问题因缺少证据，无法在阶段1完成验证：

1. **真实会话错误统计**: 需要访问 Pi Agent 日志
2. **本机全局 skills/packages**: 需要扫描 `~/.pi/agent/`
3. **工具调用错误率**: 需要总调用次数和错误分类
4. **上下文压缩实际效果**: 需要真实会话的压缩前后对比
5. **弱模型（DeepSeek v4.1 Flash）实际表现**: 需要真实任务的成功率统计

---

## 六、关键发现总结

### 6.1 已确认问题（有证据）

| 问题 | 严重程度 | 优先级 |
|------|----------|--------|
| 入口文件过大（25 KB） | P0 | 高 |
| 管道记录格式复杂 | P0 | 高 |
| 上下文压缩后规则丢失 | P1 | 高 |
| 缺少超时和有限重试 | P1 | 中 |
| TDD 不强制 | P2 | 低 |

### 6.2 无法验证问题

| 问题 | 原因 | 下一步 |
|------|------|--------|
| 434 次工具错误 | 无访问日志 | 用户提供日志路径 |
| 本机 skills 冲突 | 无访问 ~/.pi/agent/ | 用户手动扫描 |
| 弱模型错误率 | 无真实任务统计 | 试点后测量 |

### 6.3 与 pstack 对比结论

- x-rail 在核心原则上与 pstack **基本一致**
- 主要差距是**入口文件组织**和**上下文管理**
- x-rail 的严格验证机制是**差异化特性**，应保留
- 不需要完全复制 pstack 的并行编排机制

---

## 七、下一步行动

1. **继续阶段2**：设计目标架构（`target-architecture.md`）
2. **补充取证**（可选）：
   - 用户提供 Pi Agent 日志路径
   - 用户扫描 `~/.pi/agent/skills/` 并反馈冲突项
3. **开始试点**（阶段3）：选择一条最常见任务路径进行轻量化改造
