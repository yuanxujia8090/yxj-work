# x-rail 目标架构

## 当前实施口径（2026-10-17）

pstack 为主要参考，本轮用户已批准实现。当前规格以 [pstack-local-implementation-plan.md](pstack-local-implementation-plan.md) 与下方当前修订为准。历史取证及阶段3试点原文保留在折叠记录，旧建议不再作为当前规则。确定性检查不证明模型服从或提速。

- 交付分流、可验证单元、持续目标、复杂定制和长期协调按真实需要展开，不按模块数设组织门槛。
- 默认主动委派沿用户与宿主授权，短小直接完成；共享写入只有一个所有者。不设置子代理15分钟硬上限，宿主协议优先。
- 普通清单检查保留；证据模式继续 contract/work_items、state 七状态、evidence 输入摘要与必要独立审查。清单通过不等于证据模式完成，不批量迁移旧任务，不实现虚构 migrate 命令。
- `task.py frontier` 只读机器前沿复用 summary 候选与递归证据检查，保守分配共享目录/glob，检查必要审查和传递依赖。全部工作项 verified 仍须整体 finish。
- `dispatch/notify/inbox/consume` 维护 audit/coordination.json 的原运行、派发输入版本、通知与消费事实，状态只在 state。通知幂等，旧输入/旧归属拒收，accepted 不自动 verified；冷启动列未消费结果，先查询原运行。
- 分类失败、持久计数与缩小/拆分重规划遵用户限制；系统性基础设施故障停派，保存准确错误、原产物与恢复步骤。脚本不启动模型、不轮询、不建守护进程。
- 来源映射：poteto-mode/SKILL.md → 分流与上下文交接；figure-it-out/SKILL.md → 定制顺序/验证先行；autonomous-run.md → 完成谓词；orchestrate.md → 滚动前沿/队列/分类失败/版本验证/冷启动。实现说明见 skills/x-rail/modules/orchestration.md，确定性证明见 validation/，正式报告路径由父会话绑定。

<details>
<summary>历史方案、阶段1-3取证与试点记录（其中冲突建议已撤回）</summary>


**基于**: evidence.md 的取证结论  
**原则**: 第一性原理驱动，保留已有修改，不强推不删数据

---

## 一、设计原则

### 1.1 核心问题

从第一性原理出发，任务系统必须解决：

1. **模型需要理解什么？**
   - 当前目标（intent、scope、done_when）
   - 安全边界（forbidden actions、decision gates）
   - 当前状态（what's done、what's next）
   - 恢复点（如何从中断继续）

2. **什么由脚本检查？**
   - 文件完整性（contract/state 存在且可解析）
   - 证据绑定（passed 验收必须有证据）
   - 输入变化检测（SHA-256 fingerprint）
   - 状态一致性（work_items 状态 vs active_work_items）

3. **什么必须每次加载？**
   - 路由表（选择正确的 playbook）
   - 核心安全规则（cost_policy、decision_policy）
   - 恢复入口（如何读取 state.md）

4. **什么按需加载？**
   - 详细验证规则（5种观察面、evidence schema）
   - 详细恢复规则（第三方 skill 处理、原运行恢复）
   - 详细执行规则（TDD、子代理、工作项拆分）

5. **什么操作必须可重复？**
   - 读取证据（`task.py summary`）
   - 重跑验证（`task.py run`，输入未变时结果应相同）
   - 更新状态（`task.py update --progress`，幂等）

6. **什么失败可以重试？**
   - API 瞬时错误（429/503/timeout）
   - 网络抖动
   - 第三方服务暂时不可用

7. **什么失败不能重试？**
   - 代码逻辑错误（测试失败）
   - 参数错误（task.py 参数格式错误）
   - 权限错误（403/401）
   - 验证失败（expected ≠ actual）

### 1.2 设计约束

**必须保留**:
- `.work-docs/` 目录结构（已有任务依赖）
- task.py 的核心命令（start/finish/update/run）
- 证据模式机制（证据绑定、输入指纹）
- 恢复机制（state.md + checkpoint）
- 用户已有的所有任务记录

**必须改进**:
- 入口文件大小（25 KB → 5 KB）
- 上下文压缩后的恢复能力
- 弱模型的服从性
- 超时和重试策略

**可以选择**:
- 记录格式（pipe record vs Markdown checklist）
- 子代理策略（默认启用 vs 默认关闭）
- TDD 强制程度
- task.py 的角色（硬门禁 vs 可选检查器）

---

## 二、目标架构设计

### 2.1 轻量入口（5 KB 目标）

**新 `skills/x-rail/SKILL.md` 结构**:

```markdown
---
name: x-rail
description: 按交付结果分流的独立任务入口
disable-model-invocation: true
---

# x-rail

## 一、目的与授权
- x-rail 是什么
- 什么时候使用
- 调用即授权当前范围内默认主动委派
- 四类敏感动作需确认（不可逆/费用/发布/范围变更）

## 二、路由表
| 交付结果 | 路径 | playbook |
|----------|------|----------|
| 解释/调查 | investigate | playbooks/investigate.md |
| ...     | ...  | ... |

## 三、核心规则
- **记录强度判断**: failure_cost_high OR recovery_or_handoff_needed → 证据模式
- **安全边界**: forbidden actions, decision gates
- **成本策略**: cost_control: unlimited 的判断条件（简化版）

## 四、恢复入口
- 证据模式任务: 读取 .work-docs/tasks/<task-id>/state.md
- 普通任务: 续接用户补充和工具结果
- 详细恢复规则: 按需读取 modules/recovery.md

## 五、按需加载
- 详细验证规则 → modules/verification.md
- 详细执行规则 → modules/execution.md
- 详细恢复规则 → modules/recovery.md
- 详细工作项规则 → modules/work-items.md
```

**目标大小**: ~5 KB (当前 25 KB 的 20%)

**拆分原则**:
- 入口只保留"决策树"（如何选择 playbook 和 module）
- 详细规则按职责拆分到 modules/
- Playbook 保持现状（已经是按路由分离）

### 2.2 按需加载模块

**新目录结构**:

```
skills/x-rail/
├── SKILL.md (轻量入口, ~5 KB)
├── scripts/
│   ├── task.py (保持现状)
│   └── task_checks.py (保持现状)
├── playbooks/ (保持现状)
│   ├── investigate.md
│   ├── design.md
│   └── ...
├── modules/ (新增)
│   ├── verification.md (从 SKILL.md 拆出)
│   ├── execution.md (从 SKILL.md 拆出)
│   ├── recovery.md (从 SKILL.md 拆出)
│   ├── work-items.md (从 SKILL.md 拆出)
│   └── cost-policy.md (从 SKILL.md 拆出，详细版)
└── templates/ (保持现状)
    ├── contract.md
    └── ...
```

**加载时机**:
- 入口 SKILL.md: 每次调用 /x-rail 自动加载
- playbooks/<name>.md: 根据路由表选择后加载
- modules/<name>.md: 
  - 进入证据模式 → 加载 verification.md
  - 启动子代理 → 加载 work-items.md
  - 遇到中断 → 加载 recovery.md
  - 用户声明不限成本 → 加载 cost-policy.md（详细版）

**上下文压缩后恢复**:
1. 读取 state.md（包含 task_id、status、next_action）
2. 重新加载入口 SKILL.md（5 KB，轻量）
3. 按 state.md 的 task_type 加载对应 playbook
4. 按 state.md 的 status 加载对应 module（如 status=blocked → 加载 recovery.md）

### 2.3 简化任务记录（推荐方案A）

**目标**: 降低模型负担，保留机器可检查性

**新格式** (Markdown checklist):

```markdown
# Task: <task-id>

## Intent
- **Goal**: 修复 bug X
- **Scope**: 文件 A、B、C
- **Done when**: 测试通过 + 无回归

## Status
- Current: implementing
- Next: 运行测试

## Checklist
- [x] Understand: 复现 bug
- [x] Plan: 确定根因和修复策略
- [ ] Implement: 修改代码
- [ ] Verify: 运行测试
- [ ] Handoff: 提交 PR

## Evidence
### E1: 复现 bug
- Command: `pytest tests/test_auth.py::test_login_expired`
- Result: FAILED (expected)
- Path: evidence/e1-reproduce.txt

### E2: 根因分析
- Finding: token 过期检查用了 `<` 应该用 `<=`
- Source: src/auth.py:42

## Decisions
- D1: 不改 API，只修内部逻辑（影响最小）

## Risks
- R1: 其他地方可能有相同问题 → 全仓搜索 `token.expires_at <`
```

**与 task.py 的关系**:
- task.py 降级为**可选检查器**
- 默认不阻止任务完成
- 用户或 CI 可主动运行 `task.py check <task-file>`
- 检查项：
  - checklist 是否完整（必需步骤都有）
  - evidence 是否绑定（[x] 项必须有对应 evidence）
  - intent 是否明确（goal/scope/done_when 非空）

**迁移策略**:
- 旧格式（contract.md + state.md）只读兼容
- 新任务使用新格式
- 提供转换工具：`task.py migrate <task-dir>` → 生成新格式文件
- 兼容期：6 个月（2026-10 ~ 2027-04）

### 2.4 超时和重试策略

**工作项超时**: 15 分钟（硬上限）

**重试策略**:

| 错误类型 | 重试次数 | 条件 |
|----------|----------|------|
| API 瞬时错误（429/503/timeout） | 1 次 | 同一工作项内 |
| 网络抖动 | 1 次 | 同一工作项内 |
| 代码逻辑错误 | 0 次 | 不重试 |
| 参数错误 | 0 次 | 不重试 |
| 权限错误 | 0 次 | 不重试 |
| 验证失败 | 0 次 | 不重试 |

**实现**:
- 在 playbooks/exec.md 或新 modules/execution.md 中明确
- 模型判断错误类型（从工具输出的 HTTP 状态码或错误消息）
- 重试时记录：`retry_count: 1/1, reason: API timeout`
- 重试后仍失败 → 保存 checkpoint 并标记 `blocked_by: api_timeout`

### 2.5 子代理策略（保守方案）

**默认**: 单会话完成任务

**启用子代理的条件**（任一满足）:
1. 任务明确声明"启用子代理"
2. 工作项数量 >= 5 且互相独立
3. 需要并行的只读研究（如多源取证）
4. 需要独立审查（fresh context）

**约束**:
- 同一工作区只有一个写入者（主会话或子代理，不并行写）
- 子代理失败 → 主会话仍能保存 checkpoint
- 子代理输入输出记录在 `audit/runs.json`

**不启用的场景**:
- 简单任务（1-2 个工作项）
- 紧密耦合的实现（共享状态）
- 顺序依赖的步骤

### 2.6 TDD 强化

**新规则** (写入 modules/execution.md):

**默认行为**:
- 非平凡逻辑（branch/loop/parser/money/security）→ **先写失败测试**
- 纯文档、文案、简单样式 → 按实际内容核对

**TDD 流程**:
1. 理解需求和当前行为
2. 写失败测试（red）
3. 最小实现（green）
4. 重构（refactor）
5. 验证无回归

**豁免条件**:
- 测试框架不存在且无法快速设置
- 临时脚本（一次性使用）
- 用户明确要求"跳过测试"

---

## 三、迁移计划

### 3.1 阶段划分

| 阶段 | 目标 | 输出 | 风险 |
|------|------|------|------|
| **阶段1: 取证** | 确认问题和基线 | evidence.md, baseline.md | 低 |
| **阶段2: 设计** | 目标架构和迁移方案 | target-architecture.md, migration-plan.md | 低 |
| **阶段3: 试点** | 一条路径的轻量化改造 | 新格式入口 + 模块 + 转换工具 | 中 |
| **阶段4: 全面实施** | 完成所有路径的改造 | 所有文件按新架构重组 | 高 |
| **阶段5: 审查** | 独立审查和验证 | verification-report.md | 低 |

### 3.2 试点路径选择

**推荐**: `bugfix` 路径（最常见，风险可控）

**原因**:
1. bugfix 是高频路径（近14天修复类提交 20%）
2. 流程相对简单：复现 → 根因 → 修复 → 验证
3. 工作项通常少（1-3 个）
4. 容易验证效果（测试通过 = 成功）

**试点内容**:
1. 轻量化 `skills/x-rail/SKILL.md`（只保留路由和核心规则）
2. 创建 `modules/verification.md`（拆分验证规则）
3. 创建新格式模板 `templates/task-checklist.md`
4. 修改 `playbooks/bugfix.md`（引用 modules/verification.md）
5. 实现 `task.py check` 可选检查器
6. 用真实 bug 测试新流程

**成功标准**:
- 入口文件 < 5 KB
- bugfix 任务可用新格式完成
- task.py check 能正确检查新格式
- 弱模型（DeepSeek v4.1 Flash）能准确服从新规则

### 3.3 回滚策略

**每个阶段独立可回滚**:

| 阶段 | 回滚方式 | 数据丢失风险 |
|------|----------|--------------|
| 阶段3（试点） | 删除新文件，恢复旧 SKILL.md | 无（新格式任务可手动转回旧格式） |
| 阶段4（全面实施） | Git revert | 无（旧格式任务保留） |
| 阶段5（审查后） | Git revert + 迁移脚本 | 低（只影响新任务） |

**兼容期**:
- 旧格式任务永久只读兼容（不删除旧记录）
- 新旧格式共存 6 个月
- 6 个月后，旧格式只读，不再创建

---

## 四、技术细节

### 4.1 入口文件拆分

**从 SKILL.md 移出的内容** → **移入位置**:

| 章节 | 当前大小（估算） | 移入 |
|------|------------------|------|
| workflow (详细预算规则) | ~2 KB | modules/execution.md |
| cost_policy (详细判断条件) | ~2 KB | modules/cost-policy.md |
| task_directory (目录结构说明) | ~1 KB | 保留（核心） |
| execution (TDD、子代理、工具输出) | ~3 KB | modules/execution.md |
| work_items (拆分、依赖、并行) | ~2 KB | modules/work-items.md |
| lifecycle (详细状态变化) | ~1 KB | modules/execution.md |
| decision_policy (review 触发条件) | ~0.5 KB | 保留（核心） |
| verification (5种观察面、evidence schema) | ~4 KB | modules/verification.md |
| recovery (详细恢复规则) | ~3 KB | modules/recovery.md |
| output_contract (交付格式) | ~1 KB | 保留（核心） |

**保留在入口的内容** (~5 KB):
- purpose, authority (目的和授权)
- routing (路由表)
- task_directory (目录结构)
- decision_policy (核心决策门)
- output_contract (交付格式)
- 恢复入口（如何读取 state.md）
- 按需加载指引（何时读取哪个 module）

### 4.2 新格式任务文件

**单文件模式** (`task.md`):

```markdown
# Task: 20261017-01-fix-auth-timeout

## Meta
- Created: 2026-10-17T00:42:00Z
- Status: implementing
- Type: bugfix

## Intent
- Goal: 修复 token 过期检查逻辑错误
- Scope: src/auth.py
- Done when: 测试通过 + 手动验证登录流程

## Checklist
- [x] 1. Reproduce: 复现 bug
- [x] 2. Root cause: 定位根因
- [ ] 3. Fix: 修改代码
- [ ] 4. Test: 运行测试
- [ ] 5. Verify: 手动验证

## Evidence
### E1: Reproduce
- Command: `pytest tests/test_auth.py::test_login_expired`
- Exit: 1
- Output: `AssertionError: Expected 401, got 200`
- Path: evidence/e1-reproduce.txt
- Timestamp: 2026-10-17T00:45:00Z

### E2: Root cause
- Finding: Line 42 uses `<` should be `<=`
- Source: `src/auth.py:42`
- Timestamp: 2026-10-17T00:48:00Z

## Decisions
### D1: Minimal fix
- Decision: 只改运算符，不重构整个函数
- Reason: 影响最小，风险最低
- Alternatives: 重构 token 验证逻辑（成本更高）

## Next
- Action: 修改 src/auth.py:42，`<` 改为 `<=`
- Then: 运行 `pytest tests/test_auth.py`
```

**与旧格式的映射**:

| 旧格式 | 新格式 | 备注 |
|--------|--------|------|
| contract.md (goal) | Intent.Goal | 保留语义 |
| contract.md (scope) | Intent.Scope | 保留语义 |
| contract.md (done_when) | Intent.Done when | 保留语义 |
| contract.md (acceptances) | Checklist | 简化（不再用 pipe record） |
| state.md (status) | Meta.Status | 保留语义 |
| state.md (next_action) | Next.Action | 保留语义 |
| evidence/ (目录) | Evidence (章节) | 简化（不再单独目录） |
| handoff.md | 不再需要 | 新格式 task.md 本身就是交接文档 |

### 4.3 task.py 可选检查器

**新命令**: `python3 scripts/task.py check <task-file>`

**检查项**:
1. **结构完整性**:
   - 必需章节存在（Meta, Intent, Checklist, Evidence, Next）
   - Meta 字段完整（Created, Status, Type）
   - Intent 字段完整（Goal, Scope, Done when）

2. **逻辑一致性**:
   - Checklist 中 [x] 项必须有对应 Evidence
   - Evidence 的 Timestamp 按时间顺序
   - Status 与 Checklist 状态一致（所有 [x] → status: done）

3. **证据有效性**:
   - Evidence.Path 指向的文件存在
   - Evidence.Command 可解析（不验证能否执行）

**退出码**:
- 0: 所有检查通过
- 1: 结构不完整
- 2: 逻辑不一致
- 3: 证据无效

**输出**:
```
[✓] Structure: OK
[✓] Logic: OK
[✗] Evidence: E1.Path not found (evidence/e1-reproduce.txt)

Result: FAILED (1 issue)
```

**不检查的内容**:
- 是否真正解决了问题（这是用户验收）
- 代码质量（这是 linter/review）
- 测试覆盖率（这是 CI）

---

## 五、验收标准

### 5.1 结构验收

- [ ] `skills/x-rail/SKILL.md` < 5 KB
- [ ] `modules/` 目录存在，包含 4+ 模块
- [ ] 旧格式任务可只读访问（不破坏兼容性）
- [ ] 新格式任务可创建和完成

### 5.2 功能验收

- [ ] bugfix 路径可用新格式完成
- [ ] `task.py check` 能正确检查新格式
- [ ] 上下文压缩后可从 task.md 恢复
- [ ] 超时和重试策略明确记录

### 5.3 质量验收

- [ ] 弱模型（DeepSeek v4.1 Flash）能准确服从新规则
- [ ] 独立审查通过（设计 + 实现）
- [ ] 无数据丢失（旧任务保留）
- [ ] 有回滚方案

---

## 六、风险和缓解

### 6.1 已识别风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 新格式不如旧格式严格 | 高 | 中 | 保留 task.py 检查器，CI 强制运行 |
| 弱模型仍不服从 | 中 | 中 | 试点测量，必要时进一步简化 |
| 迁移成本过高 | 低 | 低 | 旧格式永久只读兼容 |
| 用户不接受新格式 | 高 | 低 | 试点反馈，允许回滚 |

### 6.2 残余风险

**试点后才能确认**:
1. 弱模型的实际服从性（需真实任务测试）
2. 新格式的易用性（需用户反馈）
3. 迁移成本（需统计旧任务数量）

**试点前无法验证**:
1. 上下文压缩后的恢复效果（需长任务测试）
2. 超时和重试的实际效果（需 API 不稳定环境测试）

---

## 七、下一步

1. **用户决策点**:
   - 批准目标架构 → 进入阶段3（试点）
   - 要求调整 → 修订本文档
   - 暂停重构 → 保留当前架构

2. **阶段3准备** (如果批准):
   - 创建 `modules/` 目录
   - 拆分 SKILL.md（保留旧版为 SKILL.md.bak）
   - 实现新格式模板
   - 修改 playbooks/bugfix.md
   - 实现 `task.py check`

3. **补充取证** (可选):
   - 用户提供 Pi Agent 日志路径
   - 用户扫描 `~/.pi/agent/skills/`

---

## 附录：与 pstack 的差异说明

**保留 x-rail 特色**:
1. 证据模式机制（证据绑定、输入指纹）
2. 契约式任务管理（intent、scope、done_when）
3. 可选的子代理（不是默认并行）

**借鉴 pstack 优势**:
1. 轻量入口 + 按需加载
2. 明确的 pause/resume checkpoint
3. 更好的上下文管理

**不复制 pstack**:
1. 不引入 `units.tsv`（x-rail 是单任务模型）
2. 不引入中心协调器（x-rail 更简单）
3. 不引入 `/recall` 技能（当前机制够用）

</details>
