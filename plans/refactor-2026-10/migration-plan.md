# x-rail 迁移计划

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


**基于**: evidence.md + target-architecture.md + pstack-comparison.md  
**原则**: 分阶段、可回滚、保留已有修改

---

## 一、迁移策略

### 1.1 核心原则

1. 增量迁移: 一次改一个路径
2. 向后兼容: 旧格式任务永久只读兼容
3. 可回滚: 每个阶段独立可回滚
4. 保留数据: 不删除旧任务记录
5. 用户选择: 试点后由用户决定是否全面实施

### 1.2 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| 新格式不如旧格式严格 | 保留task.py检查器 |
| 弱模型仍不服从 | 试点测量,必要时简化 |
| 迁移成本过高 | 旧格式永久兼容 |
| 用户不接受 | 允许回滚 |

---

## 二、阶段划分

### 阶段1: 取证 (已完成 2026-10-17)

输出: evidence.md, baseline.md, pstack-comparison.md

### 阶段2: 设计 (已完成 2026-10-17)

输出: target-architecture.md, migration-plan.md

### 阶段3: 试点（已完成）

目标: bugfix路径轻量化改造

工作项:
1. 创建modules/目录结构
2. 拆分SKILL.md(保留旧版备份)
3. 创建新格式模板
4. 修改playbooks/bugfix.md
5. 实现task.py check
6. 用真实bug测试新流程

估算: 4-6小时

成功标准:
- 入口文件<5KB
- bugfix任务可用新格式完成
- task.py check能正确检查
- 弱模型能准确服从新规则

### 阶段4: 全面实施

前提: 阶段3已完成，用户另行批准

工作项:
1. 完成所有路径改造(8个路径)
2. 更新所有playbooks/引用modules/
3. 更新参考技能引用
4. 写迁移文档和用户指南

估算: 12-16小时

### 阶段5: 审查和验证

工作项:
1. 设计审查
2. 实现审查
3. 多任务测试(5-10个真实任务)
4. 文档审查

估算: 4-6小时

---

## 三、详细实施计划

### 3.1 阶段3详细步骤

#### 步骤1: 创建目录结构 (30分钟)

```bash
mkdir -p skills/x-rail/modules
touch skills/x-rail/modules/verification.md
touch skills/x-rail/modules/execution.md
touch skills/x-rail/modules/recovery.md
touch skills/x-rail/modules/work-items.md
touch skills/x-rail/modules/cost-policy.md
```

验证: 目录存在,文件可写

#### 步骤2: 拆分SKILL.md (2小时)

2.1 备份旧版本:
```bash
cp skills/x-rail/SKILL.md skills/x-rail/SKILL.md.bak
```

2.2 从SKILL.md移出内容:

| 章节 | 移入文件 | 大小 |
|------|---------|------|
| workflow详细预算 | modules/execution.md | ~2KB |
| cost_policy详细判断 | modules/cost-policy.md | ~2KB |
| execution TDD子代理 | modules/execution.md | ~3KB |
| work_items拆分依赖 | modules/work-items.md | ~2KB |
| lifecycle详细状态 | modules/execution.md | ~1KB |
| verification 5观察面 | modules/verification.md | ~4KB |
| recovery详细恢复 | modules/recovery.md | ~3KB |

2.3 保留在SKILL.md的内容:
- purpose, authority
- routing路由表
- task_directory目录结构
- decision_policy核心决策门
- output_contract交付格式
- 恢复入口(如何读state.md)
- 按需加载指引(何时读哪个module)

目标大小: ~5KB

验证: wc -c skills/x-rail/SKILL.md < 5120

#### 步骤3: 创建新格式模板 (1小时)

创建templates/task-checklist.md,包含:
- Meta(Created, Status, Type)
- Intent(Goal, Scope, Done when)
- Checklist(步骤列表)
- Evidence(命令,退出码,输出,路径,时间戳)
- Decisions(决策,原因,替代方案)
- Next(下一步动作)

验证: 模板可读,字段完整

#### 步骤4: 修改playbooks/bugfix.md (30分钟)

添加modules/引用:
- 详细验证规则→modules/verification.md
- 详细执行规则→modules/execution.md

验证: 引用路径正确

#### 步骤5: 实现task.py check (2小时)

新命令: python3 scripts/task.py check <task-file>

检查项:
1. 结构完整性(必需章节存在)
2. 逻辑一致性([x]项有对应Evidence)
3. 证据有效性(Path指向的文件存在)

输出格式:
```
[✓] Structure: OK
[✓] Logic: OK
[✗] Evidence: E1.Path not found
Result: FAILED (1 issue)
```

退出码: 0通过,1结构不完整,2逻辑不一致,3证据无效

验证: 对合法任务返回0,对缺失返回非0

#### 步骤6: 真实bug测试 (1小时)

选择一个真实bug,执行新流程:
1. 调用/x-rail,选bugfix路径
2. 模型创建新格式任务文件
3. 按TDD流程修复
4. 运行task.py check
5. 验证任务完成

记录:
- 模型是否准确创建新格式
- 是否遗漏字段或写错格式
- task.py check是否准确
- 入口文件加载量是否减少

验证: 任务完成且测试通过,task.py check返回0,入口<5KB

---

### 3.2 阶段4详细步骤

前提: 阶段3已完成，用户另行批准继续

#### 步骤1: 完成其他路径 (8-10小时)

依次改造8个路径:
- investigate (1小时)
- research (1小时)
- design (1小时)
- plan (1小时)
- exec (2小时,最复杂)
- review (1小时)
- ops (1小时)
- mixed (1小时)

每个路径:
- 更新playbooks/<name>.md
- 添加modules/引用
- 测试一个真实任务

#### 步骤2: 更新参考技能 (2小时)

检查x-how/x-why/x-blast-radius等是否需要更新

更新引用路径,验证引用有效

#### 步骤3: 写迁移文档 (2小时)

创建docs/migration-guide.md:
1. 为什么迁移
2. 新旧格式对比
3. 如何迁移旧任务
4. 常见问题FAQ
5. 回滚方式

---

### 3.3 阶段5详细步骤

#### 步骤1: 设计审查 (2小时)

审查点:
- 入口文件是否<5KB
- 是否真的减少了模型负担
- 是否引入隐式状态
- 是否保留了安全边界
- modules/是否按需加载

输出: 设计审查报告

#### 步骤2: 实现审查 (2小时)

审查点:
- 是否有旧调用点残留
- 是否有旧格式残留
- 是否有不可重复执行的操作
- 是否有无界重试
- 是否有测试覆盖

输出: 实现审查报告

#### 步骤3: 多任务测试 (2小时)

选择5-10个真实任务:
- 覆盖所有路径
- 包含简单和复杂任务
- 用不同模型测试

记录:
- 成功率
- 错误类型分类
- 模型服从性对比

输出: 测试报告

---

## 四、回滚策略

### 4.1 阶段3回滚

触发条件: 试点失败或用户不满意

回滚步骤:
1. 恢复旧SKILL.md
2. 删除modules/
3. 删除新格式模板
4. 恢复playbooks/bugfix.md

数据丢失: 无

### 4.2 阶段4回滚

触发条件: 全面实施后发现重大问题

回滚步骤:
1. Git revert所有相关提交
2. 恢复旧版本文件
3. 运行迁移脚本(新格式→旧格式)

数据丢失: 低(只影响新任务)

---

## 五、兼容性策略

### 5.1 旧格式只读兼容

实现: task.py保留旧格式解析

功能:
- task.py summary可读取旧格式
- task.py check只检查新格式
- 旧任务不会被自动迁移

### 5.2 兼容期

时长: 6个月(2026-10~2027-04)

策略:
- 新任务使用新格式
- 旧任务只读访问
- 6个月后旧格式只读不再创建

### 5.3 迁移工具

可选: task.py migrate <task-dir>

功能:
- 读取旧格式
- 生成新格式文件
- 保留旧文件

输出: task.md(新格式) + migration.log(转换记录)

---

## 六、验收标准

### 6.1 阶段3验收

- 入口文件<5KB
- modules/目录存在,包含5个模块
- 新格式模板完整
- task.py check实现并通过测试
- 一个真实bugfix任务用新格式完成
- 弱模型能准确服从新规则

### 6.2 阶段4验收

- 所有8个路径完成改造
- 所有playbooks/引用modules/
- 迁移文档完整
- 5-10个真实任务用新格式完成
- 旧格式任务可只读访问

### 6.3 阶段5验收

- 设计审查通过
- 实现审查通过
- 测试报告完成
- 无数据丢失
- 有回滚方案

---

## 七、时间估算

| 阶段 | 估算工时 |
|------|---------|
| 阶段1-2(已完成) | - |
| 阶段3(试点) | 4-6小时 |
| 阶段4(全面实施) | 12-16小时 |
| 阶段5(审查) | 4-6小时 |
| 总计 | 20-28小时 |

---

## 八、下一步行动

### 8.1 阶段3已执行

1. 已创建 `skills/x-rail/modules/`
2. 已保留旧入口备份 `skills/x-rail/SKILL.md.bak`
3. 已完成 bugfix 试点和清单检查器
4. 已完成相关测试与静态门禁验证

### 8.2 后续行动

1. 阶段4全面迁移需另行批准
2. 若继续，先按路径逐项更新 playbooks 和引用
3. 阶段4完成后执行独立设计、实现和多任务审查

---

## 九、交付清单

### 9.1 阶段1-2已交付

- evidence.md
- baseline.md
- pstack-comparison.md
- target-architecture.md
- migration-plan.md(本文档)

### 9.2 阶段3已交付

- skills/x-rail/SKILL.md(轻量版，4,302B)
- skills/x-rail/modules/*.md(5个模块)
- templates/task-checklist.md
- task.py check实现
- 试点报告与回归输出

### 9.3 阶段4-5待交付

- 所有playbooks/更新
- 迁移文档
- 设计审查报告
- 实现审查报告
- 测试报告
- 最终交付报告

</details>
