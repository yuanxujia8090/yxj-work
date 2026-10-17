# 工作项规则

本模块定义如何拆分和管理工作项（work items）。

---

## 拆分原则

实施前按逻辑独立性、复杂度、改动范围和依赖识别工作项。

### 必须拆分的情况

- 多个独立复杂逻辑
- 跨模块或入口的大范围改动
- 单需求内多步状态/权限/并发/写入
- 协作与前置依赖

### 可以合并的情况

- 多个简单同源且可一次验证的改动可合并并说明依据
- 已有合格清单先核对覆盖并复用

### 特殊情况

- 只读分析只在回复列清单，不落盘
- 只要方案文档只写授权位置，不代建实施记录

---

## 工作项契约

新证据模式实施契约使用 `work_items_schema: 1`，定义 requirement 与 work_item。

`task.py start` 对 `task_type=exec|bugfix` 强制此字段，mixed/ops 等其他类型不由脚本猜测是否实施。

触发上述复杂度或范围条件的证据模式实施仍须显式采用 schema，不能换类型绕过。

`state` 一一记录 `work_item_state`，`active_work_items` 由 `in_progress` 项自动生成并校验一致。

整体状态与工作项七状态分开；结构与完整命令见 playbooks/verification.md。

旧记录 check/update 兼容，需要清单时显式升级契约、保留快照，不自动迁移或补造历史。

计划不维护第二份状态。

---

## 工作项七状态

1. **pending**: 尚未开始
2. **in_progress**: 正在实施
3. **awaiting_verification**: 实现完成，等待验证
4. **needs_fix**: 验证失败
5. **blocked**: 被依赖或外部条件阻塞
6. **verified**: 验证通过，证据有效
7. **skipped**: 跳过（仅适用于可选项）

---

## 拆分后核对

拆分后核对：
- 需求覆盖（所有需求都有对应工作项）
- 验收引用（工作项引用的验收在契约中存在）
- 无环依赖（没有循环依赖）
- 资源所有权（没有多个工作项同时写同一文件）

---

## 委派规则

调用 x-rail 即已获当前目标范围内委派授权；宿主可用、目标与读写范围及验收明确时，默认主动委派完整执行单元。

### 可以并行的工作项

- 独立且资源隔离的项可并行
- 有依赖项在前置满足后接力

### 不可并行的情况

- 不可并行或文件共享不是父会话包办理由
- 共享写入由同一子代理承接

### 直接完成的情况

- 短小且已掌握材料
- 交接成本明显更高时直接完成
- 紧密耦合的实现由同一位执行者承接

---

## 主会话职责

主会话负责：
- 共享约定
- 集成
- 最终验收

六条执行规则统一见 playbooks/exec.md。

---

## 子代理规则

子代理总时限沿用宿主与代理配置，默认省略 `timeoutMs/maxRuntimeMs`（子运行总时限覆盖参数），不在提示词或子任务停止条件中另设运行倒计时。

仅当前用户明确要求或更高优先级规则强制时传入，并记录来源。

任务记录总期限、无进展阈值和单条验证命令超时不转换成子代理总时限；实际超时按原运行恢复规则处理。

子任务输入与正式返回使用 `templates/child-task.md`；共享写入、结果消费和原运行恢复按 playbooks/exec.md 与本入口 recovery 执行，通知不代表已验证。

---

## 状态核对时机

以下时机核对工作项状态：
- 开始
- 实现完成
- 新验证
- 审查返回
- 阻塞/解除
- 重要阶段变化
- 提交
- 压缩
- 交接前

整体 `next_action` 只写第一可执行动作，其他待办留在工作项。

单项受阻而其他项可推进时不阻塞整体。

提交仅是事实，不能代替验收。

---

## 可选项跳过规则

可选项 `skipped` 自动引用契约非空且非 `none` 的 `skip_reason`，保留本次 `item-reason` 动作说明。

必需工作项不能 `skipped`，可选工作项合法 `skipped` 不制造 `passed`。

---

## 前置依赖处理

前置证据过期可退回待验证，无须先逐项阻塞已在做的后继。

后继保留真实既有状态，不自动级联修改。

启动或重新激活后继、进入 `verified` 及 `finish/complete` 时，仍检查前置已验证且证据当前有效。

`summary` 只读标过期事实，不能沿用旧状态放行完成。

静态定义继续校验引用和无环，不新增级联状态机。

---

## 完成门

`finish/complete` 保留全部原完成门：
- 必需项 `verified`
- 可选项明确 `verified/skipped` 且证据当前有效

才可完成。

---

## 工作项定义示例

```text
work_items_schema: 1
requirement:R1|outcome=修复 token 过期边界
work_item:W1|title=过期校验与边界测试|requirements=R1|depends=none|scope=src/auth.ts,tests/auth.test.ts|required=yes|acceptances=A1|skip_reason=none
```

定义写 contract.md 首个二级标题前，state 由 start 初始化，不将状态写回契约。

---

## 状态转换示例

```
pending → in_progress → awaiting_verification → verified (成功路径)
                                           → needs_fix → in_progress (重试)
                                           → blocked (等待依赖)
```

---

## 何时读取本模块

- 实施前：确认是否需要拆分工作项
- 写契约时：定义 requirements 和 work_items
- 更新状态时：确认状态转换规则
- 启用子代理时：确认委派规则
- 完成前：核对完成门

## 可计算前沿与接收

summary 保留原候选；需要派发时用 task.py frontier 的资源及证据检查。dispatch/notify/inbox/consume 保存原运行与接收事实，工作项状态仍用 update；完整循环、失败分类和长期恢复按 orchestration.md。
