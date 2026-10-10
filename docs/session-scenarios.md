# 会话场景记录

真实 Pi 会话中观察到的、值得留档的行为场景。只记录不处置：每条写清现象、证据和当前处置状态；决定优化时再从这里取材改 `skills/x-rail/SKILL.md`，改完注明规则修改位置与验证层级；只有实际行为验证支持时才称“已修复”，仅静态或格式回归通过则注明行为待验证。

- 本文件是仓库自带的长期参考文档（与 `architecture.md`、`file-boundary.md` 同级），不是工作流任务产物，可以不走 `.work-docs` 直接追加。
- 新条目按倒序追加在下方表格之后，编号 `SC-NNN` 递增、不复用。
- 每条附证据路径（会话 JSONL、文件路径、grep 结果），结论必须可复核。

## 0.0.3 验证状态

2026-10-10 的隔离工作区已接入严格候选完成、条件加载、有限委派、原运行恢复和只读自检。确定性测试证明程序与记录规则，不把上面历史场景写成行为已修复。固定三周窗口仍为普通入口 52 次、长入口 8 次；任务报告保存在 `.work-docs/tasks/20261010-02-implement-0-0-3/outputs/`，真实模型对照和跨会话演练另列未执行。主仓库与全局链接没有切换到该候选。

## 条目索引

| 编号 | 日期 | 一句话 | 处置 |
|---|---|---|---|
| SC-001 | 2026-10-07 | L0 判定后中途写文件不升级档位，产物落盘但无契约 | 暂不优化 |
| SC-002 | 2026-10-08 | 整理测试用例扩大为环境调查与反复规划，56 分钟后仍未交付 | 轻量分支已落地，格式回归通过；模型行为待验证 |
| SC-003 | 2026-10-09 | worktree 里改技能规则后，会话仍读到 main 的旧副本 | 合并到 main 后文件就位；模型行为未验证 |

---

## SC-003 · 分支里的技能规则改动不生效

**会话**：`01a11e82`（2026-10-09，任务 20261009-03/04 的审查会话；本地 JSONL 在 `~/.pi/agent/sessions/`）。

### 现象与证据

v2.1 分支在 worktree 里新增了阶段启动摘要、真实使用面验证和 `playbooks/verification.md`，但同一会话注入的 `yxj-work` 规则不含这些段落。原因是安装目录用的是软链，指向主仓库的工作树，而主仓库当时切在 `main`：

```text
~/.pi/agent/skills/yxj-work -> /Users/yuanxj/Documents/github/yxj-work/skills/yxj-work
```

证据：`grep -c 阶段启动摘要 ~/.pi/agent/skills/yxj-work/SKILL.md` 得 0；`test -f ~/.pi/agent/skills/yxj-work/playbooks/verification.md` 为不存在；`git -C <主仓库> branch --show-current` 为 `main`。命令输出记在 `.work-docs/tasks/20261009-04-branch-main-review-recheck/evidence/checks.txt`（本地，不随仓库分发）。

### 处置与验证边界

本次把 v2.1 快进合并到 main（见 `DECISIONS.md` 2026-10-09 第二条），软链随之读到新文件；合并后 `playbooks/verification.md` 可见，33 条软链未变。属静态与仓库状态验证：只说明“规则文件已就位”，不声称对模型行为的影响已量化。

---

## SC-002 · 测试用例整理迟迟不落笔

**会话**：`01a11a52-fce5-7703-99a1-23f753bd5778`，记录日期 2026-10-08。

### 现象与证据

原要求是结合 plans/0.0.15 和代码改动整理用例供用户测试。记录持续 56 分 34 秒，114 次工具调用；唯一写文件是第 50 分 20 秒的契约，此前已有 96 次调用，结束为 aborted。反复调查本地容器、旧验证脚本和契约格式；最后几分钟又追踪进行中的合并，而非基于固定提交写用例。

原始记录：`~/.pi/agent/sessions/--Users-yuanxj-Documents-working-website-.worktrees-1008-contact-email--/2026-10-08T07-03-28-741Z_01a11a52-fce5-7703-99a1-23f753bd5778.jsonl`，关键行：L6 原请求、L31 固定提交差异、L180 历史压缩、L249 唯一 write、L299 中止。独立统计与报告在本地 `.work-docs/tasks/20261008-01-pi-session-testcase-latency/`（不随仓库分发）。

### 处置与验证边界

已在 `skills/yxj-work/SKILL.md` 与 `playbooks/plan.md` 增加轻量文档分支：固定依据、先出初稿、补读服务具体缺口、6/20 收口、不默认搭环境或代跑。`templates/document-task.md` 保留契约与完成证据格式。`scripts/test-flow.sh` 和 `scripts/test-document-template.sh` 检查规则接入与实际模板生命周期；这些证明结构与兼容，不证明未来模型一定遵守。

实际模型试验尝试与原会话相同的 mimo-v2.6-flash-free / high，提供方返回 403：免费层只能在 OpenCode 中使用。没有同请求重试、改认证或切付费模型。三种场景（完整材料、工作区合并、关键预期缺失）的模型表现仍待验证，不能声称已提速。

---

## SC-001 · L0 判定后中途写文件不升级档位

**会话**：`01a11683-0bd5-735f-a06d-101fb4f0f5f6`
**记录日期**：2026-10-07

### 现象

用户挂载 `yxj-work` 技能，任务是"用 HTML+CSS+JS 写贪吃蛇……请直接输出完整的 HTML 文件代码"。模型把任务路由成 `fast-answer`（L0，一句话能答完的档），第一轮只在对话里贴代码、零工具调用；第二轮用户要文件路径，模型把文件写到 `~/Documents/hermes-work/archives/snake.html`（8206 字节），**没有升级到 L1，`.work-docs` 下没有契约、状态或任何任务文件**。

### 证据

- 会话 JSONL：`~/.pi/agent/sessions/--Users-yuanxj-Documents-hermes-work--/2026-10-07T13-17-29-429Z_01a11683-0bd5-735f-a06d-101fb4f0f5f6.jsonl`
  - 第 8 条记录的思考原文引用了 `SKILL.md` 路由句（"简单事实回答走 L0；需要真实读取、持久证据、修改或多阶段推进至少 L1"），并自行判定"这是直接代码输出，不是仓库工作，走 L0，不建 `.work-docs`"。
  - 第 12 条 `write` → `archives/snake.html`，第 16 条 `ls`+`tail` 验证，第 20 条 agent-summary：reads 0 / writes 1。
- 负向核对：`hermes-work/.work-docs/tasks/`（最新 20260930-01）与 `yxj-work/.work-docs/` 均 grep 不到 "snake"。

### 判定

- 第一轮判 L0 **站得住**：用户原话是"直接输出代码"，不涉及改仓库。
- 第二轮**是缺口**：写入持久文件符合第 28 行"持久证据、修改 → 至少 L1"，应升级并补建任务骨架，但模型直接落盘。`SKILL.md` 只在"预算耗尽"场景写了显式升级 level 的动作，**没有"任务性质中途变化时怎么办"**——模型从这个缝漏过去了。
- 预期纠偏：即使升级，骨架也该建在**命令执行目录**（`SKILL.md` 第 60 行：L1 以命令实际执行目录为工作根），本例是 `hermes-work/.work-docs/`，不是 yxj-work 仓库。

### 处置

暂不优化（2026-10-07 用户决定）。单次低风险一次性产物，靠模型自觉引用路由句即可。若再出现同类场景，改法是给 L0 加一句：**一旦写入任何文件即自动升 L1 并补建骨架**。
