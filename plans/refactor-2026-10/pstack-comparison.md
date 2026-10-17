# x-rail vs pstack 对比分析

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


**基于**: pstack README.md + 已索引的 100+ 技能文件  
**目的**: 识别差异，提取可借鉴的设计

---

## 一、核心设计理念对比

### 1.1 任务模型

| 维度 | pstack | x-rail |
|------|--------|--------|
| 任务粒度 | 小单元(units.tsv) | 单任务(contract+work_items) |
| 并行模型 | 默认并行+中心协调器 | 默认单会话,可选子代理 |
| 状态持久化 | 轻量(单文件checkpoint) | 重量(contract+state+evidence目录) |
| 恢复机制 | 读checkpoint即恢复 | 读contract+state+checkpoint |

**结论**: pstack适合并行多单元任务，x-rail适合证据模式任务，目标不同。

### 1.2 上下文管理

| 维度 | pstack | x-rail | 评估 |
|------|--------|--------|------|
| 入口文件 | 轻量(每个技能独立) | 重量(25KB单文件) | pstack更优 |
| 规则组织 | 分散到各技能 | 集中在入口 | pstack更优 |
| 按需加载 | 每个技能独立调用 | 全部规则一次加载 | pstack更优 |
| 压缩后恢复 | checkpoint+重新加载技能 | 依赖完整规则 | pstack更优 |

**结论**: pstack的轻量入口+按需加载是核心优势，x-rail应借鉴。

---

## 二、核心能力对比

### 2.1 pstack独有能力

| 能力 | x-rail是否需要 | 优先级 |
|------|----------------|--------|
| /recall | 当前state.md够用 | P2 |
| /reflect | meta能力,优先级低 | P3 |
| /interrogate | 可选,成本高 | P3 |
| /swarm | x-rail支持子代理,不需要swarm | P3 |

**结论**: x-rail已有how/why/blast-radius等效能力。

### 2.2 x-rail独有能力

| 能力 | pstack是否有 | x-rail优势 |
|------|-------------|-----------|
| 证据模式 | 无 | 证据留存,可审计 |
| 契约式任务 | 部分(checkpoint有intent) | 更明确的边界 |
| 状态机 | 无 | 更细粒度跟踪 |

**结论**: x-rail的证据模式是差异化特性，适合审计和合规场景。

---

## 三、核心原则对比

### 3.1 共同原则(一致)

- Never Block on the Human: 两者一致
- Sequence Verifiable Units: 两者一致
- Pause Safely: 两者一致

### 3.2 pstack更强的原则

- Guard the Context Window: pstack更激进(子代理隔离大负载)
- Make Operations Idempotent: pstack更明确
- TDD: pstack强制,x-rail只提到

**借鉴建议**: x-rail应强制TDD,明确幂等操作,但保持保守的子代理策略。

---

## 四、核心借鉴总结

### 4.1 必须借鉴(已纳入目标架构)

| pstack能力 | 借鉴方式 | 优先级 |
|-----------|---------|-------|
| 轻量入口 | SKILL.md 25KB→5KB | P0 |
| 按需加载 | 创建modules/目录 | P0 |
| TDD强制 | 非平凡逻辑默认先写测试 | P1 |

### 4.2 部分借鉴

| pstack能力 | 借鉴方式 | 优先级 |
|-----------|---------|-------|
| Guard Context Window | 入口轻量化,默认单会话 | P1 |
| Make Operations Idempotent | 明确可重复执行的操作 | P2 |

### 4.3 不借鉴

- units.tsv: x-rail是单任务模型
- 中心协调器: 复杂度不值得
- /swarm: 已有子代理机制

---

## 五、差异化特性保留

### 5.1 x-rail必须保留

- 证据模式(差异化特性,适合审计)
- 证据绑定(可追溯性)
- 契约式任务(明确边界)
- 状态机(细粒度跟踪)

### 5.2 x-rail可以放松

- task.py硬门禁→可选检查器
- 管道记录格式→Markdown checklist
- 默认证据模式→保留普通/严格模式选择

---

## 六、关键结论

1. x-rail和pstack目标不同:
   - pstack: 快速迭代、并行任务
   - x-rail: 证据模式、证据留存、审计

2. 必须借鉴的核心:
   - 轻量入口(25KB→5KB)
   - 按需加载(modules/)
   - TDD强制

3. 必须保留的特性:
   - 证据模式(work_items+evidence)
   - 单任务模型(不引入units.tsv)
   - 默认单会话(子代理可选)

4. 不需要完全对齐: x-rail的证据模式是差异化特性。

</details>
