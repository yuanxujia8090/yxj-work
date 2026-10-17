# x-rail pstack 本地执行机制交接

> 更新时间：2026-10-17
> 工作区：`/Users/yuanxj/Documents/github/x-rail/.worktrees/v3`
> 分支：`v3`
> 当前 `HEAD`：`b158f20de87d361829e9c6ed821cbc8d7b3accd0`

## 下一会话第一步

1. 进入上述工作区，执行 `git status --short`、`git diff --check`、`git diff --cached --stat`。
2. 读取本文件、[实施计划](pstack-local-implementation-plan.md)、[交付报告](delivery.md) 和 `DECISIONS.md` 当前条目。
3. 核对 `plans/refactor-2026-10/validation/closeout-workspace-final.json` 与当前工作区文件清单，确认没有新的外部修改。
4. 读取规范复核 [standards-final.md](/Users/yuanxj/.pi/agent/sessions/--Users-yuanxj-Documents-github-x-rail-.worktrees-v3--/subagent-artifacts/outputs/72b5596d-f882-4d5e-90b8-8b1ff89eb6ee/pstack-local/standards-final.md) 和需求复核 [spec-final.md](/Users/yuanxj/.pi/agent/sessions/--Users-yuanxj-Documents-github-x-rail-.worktrees-v3--/subagent-artifacts/outputs/72b5596d-f882-4d5e-90b8-8b1ff89eb6ee/pstack-local/spec-final.md)。两份复核均为 PASS/OK。
5. 若文件清单与审查输入一致，运行最终冻结前检查，再按当前用户已授权的实现任务选择性暂存并提交；不要推送。

## 已完成

本轮已按 pstack 主要原则完成本地适配：统一原则、按交付性质分流、按实际协调需要增加编排深度。没有引入固定“轻量/大任务”模式，也没有工作项数量阈值。

已实现并接通：

- `task.py frontier`：只读计算就绪、执行中、等待验证、阻塞、过期和终态，复用现有工作项状态、传递依赖、证据和审查检查，保守处理共享路径、父子路径和通配路径冲突。
- `dispatch/notify/inbox/consume`：在 `audit/coordination.json` 保存原运行、稳定前置输入、通知、消费和失败分类事实；通知幂等，晚到和旧结果不能自动通过，消费不授予 `verified`。
- 稳定前置与可变产物分开：`dispatch.inputs` 只绑定执行期间应保持稳定的前置/共享约定；执行者预期修改的工作范围不放入该输入。无稳定文件前置使用 `--inputs none`，不造占位文件。
- 终态边界已修复：`done/cancelled` 任务拒绝不同事件号的新通知；相同事件内容保持幂等，冲突内容拒绝；完成门未放松。
- 真实事件时间边界已修复：允许事件时间早于运行登记时间，继续拒绝未来时间，并保留原运行、契约、前置和产物核验。
- 清单和证据软链接边界已修复：清单文件、父目录、证据文件及中间目录软链接均拒绝；路径解析后仍需位于任务目录内。
- `scripts/test-worktree.sh` 支持 `--keep-artifacts`。测试专用临时夹具可以在新目录内 `git add/commit` 验证工作副本行为；主工作区未暂存、未提交。
- 方案、入口、模块、模板、playbooks、README、架构说明和交付记录已同步。

## 验证证据

实施者留下并由独立审查者核读的结果：

- `test-task-checks.py`：72 项，OK。
- `test-work-items.py`：17 项，OK。
- `test-task-checklist.py`：修复后 7 项，OK。
- `test-coordination.py`：修复后 11 项，OK。
- `test-frontier.py`：5 项，OK。
- `test-self-check.py`：15 项，OK。
- `test-skill-xml.py`：4 项，OK。
- `test-repo-boundary.py`：1 项，OK。
- `test-flow.sh`：6 个静态规则组、10 条路由，passed。
- `test-worktree.sh --keep-artifacts`：16 cases，passed。
- `test-contract.sh --keep-artifacts`、`test-fixtures.sh`、`test-v2-lifecycle.sh`：passed。
- `test-document-template.sh`、`check-repo.sh`、技能元数据 24 cases：passed。
- `py_compile`、四个模块独立导入、`git diff --check`：passed。
- pyright 1.1.414 / Python 3.10：实际检查 11 个文件，`0 errors, 0 warnings, 0 informations`。
- 模拟宿主公开 CLI 演练：36 次调用，PASS。
- 修复前后反例：`validation/closeout-coordination-red-confirmed.txt` → `closeout-coordination-green.txt`；`closeout-checklist-red.txt` → `closeout-checklist-green.txt`。
- 父会话补充的仓库、安装、元数据和模板检查见 `validation/parent-additional-checks.md`。

## 独立审查

固定审查基线为 `b158f20de87d361829e9c6ed821cbc8d7b3accd0`。规范轴和需求轴首次审查发现三项问题：终态晚到通知死结、登记前真实事件被拒、软链接逃逸。实施者修复后，原两位审查者定向复核均通过：

- 规范复核：`Merge verdict: PASS`，`No issues found`。
- 需求复核：`Merge verdict: OK`，`No issues found`。

审查期间没有把实施者自报当作通过依据；审查者读取了当前源码、测试、红绿日志和保留夹具。完整固定基线证据在 `validation/` 下的 `review-baseline-evidence/`。

## 未完成与边界

- 仍未完成父会话的最终冻结复核和 `git add` / `git commit`。提交是本轮用户已授权的最后动作；不要推送。
- 工作区已有上一阶段修改和本轮全部修改，必须整体保留；提交前核对清单，避免只提交新增源码而漏掉配套文档或阶段3文件。
- 不要把确定性测试、模拟宿主或静态检查说成真实模型服从、跨日稳定性、费用、API 长尾或整体提速证明。
- 初次失败的宿主实施运行因 `Subagent timed out after 1800000ms` 中断；随后通过原协议恢复完成。一次 closeout 因 `upstream_error · The service is temporarily unavailable. Please retry later.` 中断；随后同协议恢复完成。它们是历史过程，不是当前代码失败。
- 当前 `delivery.md` 仍保留历史阶段1-3折叠内容，其中旧的选择性 pstack 结论只作为历史记录；当前口径以文档顶部和本轮实施计划为准。

## 推荐收尾命令

```bash
cd /Users/yuanxj/Documents/github/x-rail/.worktrees/v3

git status --short
git diff --check
bash scripts/check-repo.sh
python3 scripts/test-task-checks.py
python3 scripts/test-work-items.py
python3 scripts/test-task-checklist.py
python3 scripts/test-frontier.py
python3 scripts/test-coordination.py
python3 scripts/test-repo-boundary.py
bash scripts/test-flow.sh
```

完成上述冻结前核对后，选择性暂存本轮实现、验证脚本、方案和交付文档，检查 `git diff --cached --stat` 与 `git diff --cached --check`，提交当前 `v3`。不要执行 push、全局安装、发布、删除或清理。
