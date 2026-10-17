# x-rail 重构阶段1-2 交付报告

## 当前实施口径（2026-10-17）

pstack 为主要参考，本轮用户已批准实现。当前规格以 [pstack-local-implementation-plan.md](pstack-local-implementation-plan.md) 与下方当前修订为准。历史取证及阶段3试点原文保留在折叠记录，旧建议不再作为当前规则。确定性检查不证明模型服从或提速。

- 交付分流、可验证单元、持续目标、复杂定制和长期协调按真实需要展开，不按模块数设组织门槛。
- 默认主动委派沿用户与宿主授权，短小直接完成；共享写入只有一个所有者。不设置子代理15分钟硬上限，宿主协议优先。
- 普通清单检查保留；证据模式继续 contract/work_items、state 七状态、evidence 输入摘要与必要独立审查。清单通过不等于证据模式完成，不批量迁移旧任务，不实现虚构 migrate 命令。
- `task.py frontier` 只读机器前沿复用 summary 候选与递归证据检查，保守分配共享目录/glob，检查必要审查和传递依赖。全部工作项 verified 仍须整体 finish。
- `dispatch/notify/inbox/consume` 维护 audit/coordination.json 的原运行、派发输入版本、通知与消费事实，状态只在 state。通知幂等，旧输入/旧归属拒收，accepted 不自动 verified；冷启动列未消费结果，先查询原运行。
- 分类失败、持久计数与缩小/拆分重规划遵用户限制；系统性基础设施故障停派，保存准确错误、原产物与恢复步骤。脚本不启动模型、不轮询、不建守护进程。
- 来源映射：poteto-mode/SKILL.md → 分流与上下文交接；figure-it-out/SKILL.md → 定制顺序/验证先行；autonomous-run.md → 完成谓词；orchestrate.md → 滚动前沿/队列/分类失败/版本验证/冷启动。实现说明见 skills/x-rail/modules/orchestration.md，确定性证明见 validation/，正式报告路径由父会话绑定。

## 审查修复续接（2026-10-17，当前结果）

基线/HEAD 仍为 `b158f20de87d361829e9c6ed821cbc8d7b3accd0`，分支 v3。读取 `validation/spec-review-full-recovered.md`、规范轴原报告与 `validation/reviewer-public-counterexamples.json`，按实际代码核对三类发现均成立。上游错误未产出的修复从现场继续；全部已有阶段3、本轮修改和恢复快照保留。此段为当前结果，折叠区历史计数不代表修复后结果。

| 发现 | 根因修复 | 公开 CLI 反例证据 |
| --- | --- | --- |
| P1：done 后新通知令完成门和消费接口锁死 | done/cancelled 新事件在保存前拒绝；原事件相同内容重放幂等、冲突内容拒绝。未放松 check_closed/finish | `closeout-coordination-red-confirmed.txt` → `closeout-coordination-green.txt`；完成/取消后 inbox、consume 原事件、check 通过，任务全部文件字节不变 |
| P1：真实早到结果被登记时间下界拒收 | 移除 registered_at 下界；保留原 observed_at、未来时间拒绝、原运行和版本核对 | 同上；真实产物先完成、记录实际时间、跨秒后登记运行、通知和消费 accepted；未来时间拒绝且协调记录不变 |
| 规范轴 P1/需求轴 P2：普通清单及证据软链越界 | CLI 将原始路径传给清单检查器；检查清单文件及父目录软链后解析。证据复用 `_safe_task_path`；共享校验拒绝任意证据目录/文件软链并保留解析后归属检查 | `closeout-checklist-red.txt` → `closeout-checklist-green.txt`；清单文件/父目录、外部证据文件/父目录、内部证据文件/父目录共6类均拒绝，直接调用与 CLI 均覆盖 |

本次修复源码：`skills/x-rail/scripts/coordination.py`、`task_checks.py`、`task.py`；测试：`scripts/test-coordination.py` 新增2个测试方法（含 done/cancelled 两分支）、`scripts/test-task-checklist.py` 新增1个测试方法（6类软链）；同步 `skills/x-rail/modules/orchestration.md` 和实施计划/本报告。dispatch 稳定前置、消费不等于验收、现有 run/record 与完成门验证产物当前版本均保留。

以下命令均在当前工作区执行，日志前缀为 `plans/refactor-2026-10/validation/`：

| 命令 | 结果 | 日志 |
| --- | --- | --- |
| `python3 scripts/test-coordination.py`（实现前/后） | 确认红测：11项、3反例失败；修复后11项全部OK | `closeout-coordination-red-confirmed.txt` / `closeout-coordination-green.txt` |
| `python3 scripts/test-task-checklist.py`（实现前/后） | 红测：7项、6类反例失败；修复后7项全部OK | `closeout-checklist-red.txt` / `closeout-checklist-green.txt` |
| `python3 scripts/test-task-checks.py` | 72 tests，OK（包含工作项测试，不与下行相加计数） | `closeout-task-checks.txt` |
| `python3 scripts/test-work-items.py` | 17 tests，OK | `closeout-work-items.txt` |
| `python3 scripts/test-frontier.py` | 5 tests，OK | `closeout-frontier.txt` |
| `python3 scripts/test-self-check.py` | 15 tests，OK | `closeout-self-check.txt` |
| `python3 scripts/test-skill-xml.py` | 4 tests，OK | `closeout-skill-xml.txt` |
| `python3 scripts/test-repo-boundary.py` | 1 test，OK；消费者记录未变 | `closeout-repo-boundary.txt` |
| `python3 scripts/demo-coordination.py` | PASS，36次公开CLI调用 | `closeout-rehearsal.txt` |
| `bash scripts/test-flow.sh` | 6静态规则组、10路由，通过 | `closeout-flow.txt` |
| `bash scripts/test-contract.sh --keep-artifacts` | passed | `closeout-contract.txt` |
| `bash scripts/test-fixtures.sh` | passed | `closeout-fixtures.txt` |
| `bash scripts/test-v2-lifecycle.sh` | passed | `closeout-v2-lifecycle.txt` |
| `bash scripts/test-document-template.sh` | 初始封存、未完成拒绝/状态不变、完成候选及安装副本消费者通过 | `closeout-document-template.txt` |
| `bash scripts/check-repo.sh` | passed | `closeout-repo.txt` |
| `python3 -m py_compile skills/x-rail/scripts/*.py scripts/*.py` | exit 0 | `closeout-compile.txt` |
| 独立Python进程导入 task、task_checks、frontier、coordination（各一次） | 4模块全部通过 | `closeout-imports.txt` |
| `npm exec --yes --package pyright -- pyright --project /private/var/folders/8n/8hn9tlpx3j18cjtc3brs11j40000gn/T/x-rail-closeout-pyright-1pmneu76/pyrightconfig.json --stats` | Python 3.10，实际检查11文件，0 errors/warnings/informations；临时npm缓存执行，未全局安装 | `closeout-types-stats.txt` |
| `git diff --check`、`git diff --cached --exit-code` | exit 0；暂存差异为空 | `closeout-diff-check.txt`、最终工作区记录 |

类型检查边界：首次 `npm exec --yes --package pyright -- pyright skills/x-rail/scripts scripts` 返回13项错误（既有XML测试空spec和动态导入路径未配置），日志 `closeout-types.txt` 保留。首次临时配置的绝对include被工具忽略，`closeout-types-current.txt` 的0 errors无效，不作通过证据。最终相对include + extraPaths配置实际检查全部运行源码5文件及受影响测试/演练6文件，`closeout-types-checked.txt` 和 `closeout-types-stats.txt` 可复核。初次协调红测含夹具初始化错误，另存 `closeout-coordination-red.txt`；确认红测已修好夹具且在改源码前执行。

保留路径：36调用演练任务为 `/private/var/folders/8n/8hn9tlpx3j18cjtc3brs11j40000gn/T/x-rail-task-yx7_eio6/.work-docs/tasks/new-task`，完整调用在该目录 `outputs/rehearsal.json`；新增反例夹具在 green/red 日志 `KEEP` 行；文档安装副本和仓库边界夹具在对应日志。父会话此前的安装/元数据24项/模板/仓库证据见 `validation/parent-additional-checks.md`，安装与元数据未在本修复重复跑。

限制：修复后独立审查尚待父会话执行，不自授予最终GO。确定性CLI与模拟宿主不证明真实模型服从、费用、跨日稳定性、API长尾改善或提速。未暂存、提交、推送、发布、全局安装、删除或清理；父会话最终复核并提交。

<details>
<summary>历史方案、阶段1-3取证与试点记录（其中冲突建议已撤回）</summary>


**日期**: 2026-10-17  
**分支**: v3 (worktree)  
**阶段**: 阶段1(取证) + 阶段2(设计)

---

## 一、已完成内容

### 1.1 阶段1: 取证(已完成)

**输出文档**:
1. evidence.md (14.6KB): 现状确认、问题验证、无法验证项
2. baseline.md (3.0KB): 文件大小基线、提交分析基线
3. pstack-comparison.md (3.9KB): 核心设计理念对比、能力对比

**关键发现**:
- 入口文件过大(25KB)是核心问题
- 72%的规则内容可按需加载
- 近14天门禁相关修复占22.5%
- 无法验证真实会话错误(需用户提供日志路径)

### 1.2 阶段2: 设计(已完成)

**输出文档**:
1. target-architecture.md (16.9KB): 第一性原理分析、轻量入口设计、按需加载模块
2. migration-plan.md (8.7KB): 分阶段迁移策略、详细实施计划、回滚策略

**核心设计**:
- 入口SKILL.md压缩到~5KB
- 创建modules/目录(verification/execution/recovery/work-items/cost-policy)
- 简化任务记录(Markdown checklist替代pipe record)
- task.py降级为可选检查器
- 明确超时和重试策略(15分钟、API错误重试1次)

---

## 二、证据总结

### 2.1 已确认的问题(有证据)

| 问题 | 证据 | 优先级 |
|------|------|--------|
| 入口文件过大(25KB) | wc -c | P0 |
| 管道记录格式复杂 | task.py源码 | P0 |
| 上下文压缩后规则丢失 | 用户反馈 | P1 |
| 缺少超时和重试 | recovery章节 | P1 |
| 门禁问题频繁(22.5%) | Git提交分析 | P1 |

### 2.2 无法验证的问题(待补充)

| 问题 | 原因 | 获取方式 |
|------|------|----------|
| 434次工具错误 | 无访问日志 | 用户提供日志路径 |
| 本机skills冲突 | 无访问~/.pi/agent/ | 用户手动扫描 |
| 弱模型错误率 | 无真实任务统计 | 试点后测量 |

---

## 三、设计决策

### 3.1 采纳pstack的设计

- 轻量入口(SKILL.md 25KB→5KB)
- 按需加载(创建modules/目录)
- TDD强制(非平凡逻辑默认先写测试)

### 3.2 保留x-rail的设计

- 证据模式(work_items+evidence+input fingerprint)
- 单任务模型(不引入units.tsv)
- 默认单会话(子代理可选)

### 3.3 不采纳pstack的设计

- 并行+协调器(复杂度不值得)
- units.tsv(x-rail是单任务模型)
- /swarm(已有子代理机制)

---

## 四、迁移策略

| 阶段 | 目标 | 估算 | 状态 |
|------|------|------|------|
| 阶段1: 取证 | 确认问题和基线 | - | 已完成 |
| 阶段2: 设计 | 目标架构和迁移方案 | - | 已完成 |
| 阶段3: 试点 | bugfix路径轻量化改造 | 4-6h | 已完成 |
| 阶段4: 全面实施 | 完成所有路径改造 | 12-16h | 待另行批准 |
| 阶段5: 审查 | 独立审查和验证 | 4-6h | 待阶段4完成 |

**试点路径**: bugfix(最常见、风险可控)

**成功标准**:
- 入口文件<5KB
- bugfix任务可用新格式完成
- task.py check能正确检查
- 弱模型能准确服从新规则

**回滚策略**: 每个阶段独立可回滚、无数据丢失风险

---

## 五、验收标准

### 5.1 阶段1-2验收(已完成)

- evidence.md完成(14.6KB)
- baseline.md完成(3.0KB)
- pstack-comparison.md完成(3.9KB)
- target-architecture.md完成(16.9KB)
- migration-plan.md完成(8.7KB)
- 关键问题已确认(入口过大、记录复杂)
- 设计决策已明确(轻量入口、按需加载、TDD强制)

### 5.2 阶段3验收(已完成)

- 入口文件 4,302B，低于 5KB
- modules/目录存在，包含5个模块
- 新格式模板完整且可被检查器通过
- task.py check已实现并通过测试
- 一个真实bugfix试点已完成
- 弱模型服从性尚未量化，留作后续观测

---

## 六、残余风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 弱模型仍不服从 | 中 | 高 | 试点测量、进一步简化、必要时回滚 |
| 新格式不如旧格式严格 | 低 | 高 | 保留task.py检查器 |
| 迁移成本过高 | 低 | 中 | 旧格式永久只读兼容 |
| 用户不接受 | 低 | 高 | 允许回滚 |

---

## 七、下一步决策点

### 7.1 当前状态

- 目标架构已批准
- 阶段3 bugfix试点已完成
- 阶段4全面迁移尚未批准
- 弱模型服从性、压缩后恢复效果和真实运行层效果尚未量化

### 7.2 后续行动

如继续全面迁移，先另行明确阶段4范围，再逐路径实施和验证。

---

## 八、交付物清单

### 8.1 已交付(2026-10-17)

| 文件 | 大小 | 内容 |
|------|------|------|
| evidence.md | 14.6KB | 取证报告 |
| baseline.md | 3.0KB | 基线指标 |
| pstack-comparison.md | 3.9KB | pstack对比分析 |
| target-architecture.md | 16.9KB | 目标架构设计 |
| migration-plan.md | 8.7KB | 迁移计划 |
| 总计 | 47.1KB | 5份文档 |

### 8.2 阶段3已交付

| 交付物 | 状态 |
|--------|------|
| SKILL.md轻量版 | 已交付，4,302B |
| modules/5个模块 | 已交付 |
| task-checklist.md模板 | 已交付 |
| task.py check | 已交付并通过回归 |
| 试点报告 | 已交付 |

### 8.3 本轮全面实施与验证（2026-10-17）

- 已完成前沿查询、持久协调、入口/模块/模板/README/docs 联通、稳定前置语义和 contract-only `--inputs none`。执行者预期修改的 scope 文件不作为 dispatch 输入；consume 只接收归属与前置适用性，不授予 verified。
- 红绿证据：`validation/frontier-red.txt` → `validation/frontier-green.txt`；`validation/coordination-red.txt`、`coordination-extra-red.txt` → `validation/coordination-green.txt`；`validation/repo-red.txt` → `validation/repo-green.txt`。
- 全套回归：`validation/full-*.txt`，包括 Python 10 组、shell 5 组及新增 frontier/coordination/repo-boundary 三组；新增测试计数分别为 frontier 5、coordination 9、repo-boundary 1。`validation/rehearsal-final.txt` 为公开 CLI 闭环演练。
- `test-worktree.sh --keep-artifacts` 保留临时夹具与日志；夹具内 `git -C` 的 add/commit 经父会话批准，主工作区未暂存。
- 类型/语法：`validation/types-current.txt` 与 `python3 -m py_compile`；`git diff --check` 无输出。

### 8.4 待交付(阶段4-5)

| 阶段 | 待交付物 |
|------|----------|
| 阶段4 | 所有playbooks/更新、迁移文档、全面实施报告 |
| 阶段5 | 设计审查、实现审查、测试报告、最终交付报告 |

---

## 九、总结

### 9.1 关键成果

1. 确认了核心问题(有证据): 入口过大、记录复杂、上下文压缩风险
2. 设计了目标架构: 轻量入口+按需加载、简化记录、明确策略
3. 制定了迁移计划: 分阶段、可回滚、保留数据

### 9.2 与pstack对比结论

- x-rail在核心原则上与pstack基本一致
- 主要差距是入口文件组织和上下文管理(已纳入目标架构)
- x-rail的证据模式是差异化特性,应保留
- 不需要完全复制pstack的并行编排机制

### 9.3 下一步

**当前结论**: 阶段1-2、阶段3试点及本轮 pstack 本地执行机制已实现并完成本地验证；双轴独立审查与最终提交由父会话负责。

</details>
