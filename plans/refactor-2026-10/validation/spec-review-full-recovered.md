## Review

**Merge verdict：BLOCK。发现 2 项 P1、1 项 P2；前两项应在合入前修复。**

审查基线为 `b158f20de87d361829e9c6ed821cbc8d7b3accd0`，分支 `v3`。已结合 `watchdog_diff`、父会话提供的固定基线 patch、未跟踪清单，核对源码、测试、方案和指定 pstack 上游资料。未编辑文件、执行 shell、运行测试或安装。

- **Correct：核心机制已落到实现。**
  - [frontier.py:27](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/frontier.py:27) 只读计算候选，结合活动项、未解决原运行及 scope 冲突分配资源；父子路径和不确定 glob 保守串行。
  - [task_checks.py:553](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/task_checks.py:553) 递归核验前置证据及必要审查；[work_items.py:189](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/work_items.py:189) 复用当前有效性计算，阻塞项不拖住独立兄弟项。
  - [coordination.py:209](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/coordination.py:209) 区分消费与验证，核对原运行、契约、稳定前置和归属；`accepted` 不修改工作项、不授予 `verified`。支持 `--inputs none`，没有强行绑定预期会修改的产物。
  - [orchestration.md:21](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/modules/orchestration.md:21) 串联派发、通知、消费、验证、更新、补位和最终完成门。Python 负责记账，宿主负责模型与恢复，符合本地适配边界。
- **Fixed：无。** 本轮只读审查。

### Finding：P1，完成后新通知使任务进入公开 CLI 无法消解的状态

**位置：** [coordination.py:166](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/coordination.py:166)、[task_checks.py:719](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/task_checks.py:719)。

**触发：** 原运行已消费、验收完成并 `finish` 后，同一原运行收到新的 event ID。

`notify` 在写入前调用 `context`，此时完成检查通过，随后保存新 pending event。之后 `inbox`、`consume` 同样先调用 `context → check_state → check_closed`，因未消费事件直接失败。`consume` 中原本用于终态拒收的分支因此不可达；`update` 又禁止修改终态任务。

**影响：** 一次晚到通知即可使已完成任务的 `check` 失败，正常消费命令也无法恢复。违反规格第 3、4 节的持久接收、晚到结果处理和完成闭环要求。

**动态证据：** 父会话提供的 [reviewer-public-counterexamples.json:7](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/plans/refactor-2026-10/validation/reviewer-public-counterexamples.json:7) 记录：

| 操作 | 退出码 |
| --- | --- |
| `finish` | 0 |
| 完成后 `notify` | 0 |
| `inbox`、`consume`、`check` | 均为 1 |

后三项准确错误为 `coordination has unconsumed notifications; reconcile before completion`。这是已读取的父会话运行记录，不是本审查者重跑。

**最小修复：** 终态新通知在写入前安全拒绝，或直接保存为已拒收事实，避免制造无法消费的 pending event；保留相同事件重放幂等。新增“完成后新 event ID”公开 CLI 测试，要求操作后任务检查仍通过。

### Finding：P1，登记时间下界拒绝合法的先完成、后登记事件

**位置：** [coordination.py:160](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/coordination.py:160)、[coordination.py:172](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/coordination.py:172)；流程约定见 [orchestration.md:23](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/modules/orchestration.md:23)。

**触发：** 宿主启动后才返回运行号；短运行在 `dispatch` 登记前已经完成，或启动故障发生于登记前。跨秒即可出现：

```text
宿主结果发生：10:00:00
dispatch 登记：10:00:01
notify observed-at：10:00:00
```

文档允许创建后立即登记，并要求 `observed-at` 保存真实发生时间；实现却强制 `observed_at >= registered_at`，返回 `event time must follow dispatch and not be in the future`。

**影响：** 已知原运行的真实结果不能入队，原运行持续占用资源、阻止完成。重试同一真实时间仍失败；只能篡改时间或绕过记录，均违反原事实要求。

**证据等级：** 静态代码与支持流程的直接矛盾，尚无动态复现日志。

**最小修复：** 将宿主开始时间与登记时间分开；若没有可信开始时间，取消以登记时间作为事件下界，继续保留未来时间、原运行及版本核验。补“宿主先完成、随后登记、按真实时间通知”CLI 反例，并修正文档时间约束。

### Finding：P2，普通清单证据路径可经软链逃出任务目录

**位置：** [task_checks.py:108](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/scripts/task_checks.py:108)；契约依据为 [task-checklist.md:26](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/skills/x-rail/templates/task-checklist.md:26)。

**触发：** 清单填写 `Path: evidence/e2.txt`，该路径为指向任务外非空文件的软链。

检查器仅拒绝字面绝对路径和 `..`，随后 `is_file/read_bytes` 跟随软链，仍返回 `PASSED`。父会话 [反例记录:69](/Users/yuanxj/Documents/github/x-rail/.worktrees/v3/plans/refactor-2026-10/validation/reviewer-public-counterexamples.json:69) 已记录退出码 0。

**影响：** “任务目录内证据”约束可被绕过，清单通过依赖任务外文件。此问题影响普通清单检查，不等于严格完成门绕过。

**最小修复：** 复用已有任务内路径校验，确认解析后路径仍在任务目录内，并按既有策略拒绝软链。另注意清单文件本身在 `resolve()` 后才检查 `is_symlink()`，已经丢失链接信息；对应反例同样通过。补文件及目录软链反例。

### 验证与剩余风险

已读取历史日志：frontier 5 项、coordination 9 项、task-checks 72 项均通过；模拟宿主演练记录 36 次公开 CLI 调用。父会话补充日志支持隔离复制/链接安装、24 项元数据和安装副本消费者检查通过。现有 coordination 测试未覆盖前两项时间与终态边界，清单测试未覆盖软链逃逸。

修复后应重跑协调、前沿、清单及原任务完成门回归，再运行模拟闭环。确定性 CLI 与模拟宿主证据不能证明真实模型服从率、跨日稳定性、费用或提速。明确撤回的历史方案不作为当前缺陷依据。
