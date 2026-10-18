# 附录：三份报告逐条甄别

> 主方案见 [README.md](README.md)。本表把两份源码审查报告的编号，逐条映射到 4 个根因（A/B/C/D），并给出判定。
> 判定口径：
> - **真问题**：我复核（★）或机制确认（机制）
> - **已修**：当前提交已覆盖
> - **重复**：与另一份报告的某条同源
> - **删除**：应删代码而非实现
> - **范围外**：P2 杂项，本次不处理
> - **存疑**：本机未复现，保留待验
>
> 根因代号：**A** 扩展控制平面无协调者 ｜ **B** 磁盘写入非原子/无锁 ｜ **C** 完成门不绑判据 ｜ **D** 两套模型并行与续跑越权
> 反例见主方案 §6.2；处置见 §6.3。

## 1. 两份源码报告的重复关系

两份报告独立审查、编号不同，但指向同一批根因。这张表本身是「根因少、症状多」的旁证。

| 缺陷 | `review`（3c8488a） | `gork`（d6fc6a1） | 根因 |
|---|---|---|---|
| 正常回答误判 | M1 | 已在「做得好的地方」确认修复 | **已修** |
| 无 run 会话共用计数 | M2 | P0-3 | A |
| verify 缓存不认命令 | M3 | P1-2 | C |
| done 可被改写 | M4 | P2-3 | C |
| gate 无关闭路径 | M6 | P1-8 | C |
| run_dir 逃逸 | M7 | — | B |
| import 假成功 | M8 | P2-14 | C |
| 无锁 + 非原子写 | M9 | P1-1 | B |
| 安装测试假通过 | M10 | P1-11 | C |
| 压缩空消息 | M12 | P1-5 | A |
| lockedToFallback 不清零 | M13 | P1-4 | A |
| entries 覆盖 | M14 | P2-7 | A |
| Python 3.9 | — | P1-9 | B |
| state 并发写 | C9 | P1-10 | B |
| 看门狗暂停无上限 | M11 | — | A |
| 入口两套模型 | C1 | （验收 §6.3 不满足） | D |

## 2. `gork-20261017-x-rail-v3-代码审查报告.md`

| 编号 | 问题 | 根因 | 判定 |
|---|---|---|---|
| P0-1 | 看门狗中止后不触发 E5 | A | 真问题（机制★：`agent-session.js:1426` abort 跳过 `before_settle`；`loader.js:478` 模块隔离） |
| P0-2 | `before_settle` 里 `compact()` 取消续跑 | A | 真问题（机制★：`agent-session.js:2202`、`1547-1548`） |
| P0-3 | 无 run 会话共用 `"session"` 桶，永不重置 | A | 真问题★（`x-failover.ts:70`；`store.ts` 无清理路径） |
| P0-4 | 分类器不匹配 pi 真实错误格式 | A | 真问题★（`classify.ts` 用 `/HTTP\s*401\b/`；`x-failover.ts:115` 不传 `status`） |
| P1-1 | `xr` 无锁、非原子写 | B | 真问题★（lost update 实测确认；重复派发本机未复现） |
| P1-2 | verify 缓存不认命令、空 scope 可 VERIFIED、done 不检查状态 | C | 真问题★（前两项实测确认） |
| P1-3 | `sameModelRetries` 永不清零 | A | 真问题★（`switch.ts` `memoryAfter` 只在 switch 归零） |
| P1-4 | failback 三死角（E2/E4 不切回、锁定永久、探活空转） | A + 删除 | 真问题★（`failback.ts:29`、`breaker.ts:83-85`、`applyProbe` 无调用方） |
| P1-5 | 压缩补充摘要发送空消息 | A | 真问题★（`x-run-guard.ts:175` `{ messages: [] }`） |
| P1-6 | 有 ACTIVE 即强制续跑（含向用户提问） | D | 真问题★（`guard-core.ts:25-43` 只看 outcome/active/doneMet/gate） |
| P1-7 | 「熔断并发减半」不生效 | B + 删除 | 真问题★（`xr:157` 读 `X_FAILOVER_STATE`，扩展写默认路径；`subagent.ts` 无消费者） |
| P1-8 | gate 不能关闭 | C | 真问题★（无 `resolve`；blocked 单元 `plan add` 被拒；实测确认） |
| P1-9 | Python 3.9 崩 | B | 真问题★（`frontier.py:19`；本机 3.9.6 `TypeError` 实测） |
| P1-10 | `x-failover.json` 并发丢数据 | B | 真问题★（`store.ts:35-37` 固定 tmp 名 + 无锁） |
| P1-11 | 安装旧布局残留 / 测试失败 / check-repo 未覆盖 | C | 真问题★（`test-install-v3.sh` 断言不存在路径；本机因 bash 3.2 假通过） |
| P2-1 | scope 软链读到仓库外 | C | 真问题（机制；`xr:181-193`） |
| P2-2 | U+2028 破坏整表可读性 | B | 真问题（机制；`xr:53-56` 与 `splitlines()` 不匹配） |
| P2-3 | fail 不检查状态 | C | 真问题★（= `review` M4） |
| P2-4 | verify 超时丢输出 + 孤儿进程 | B | 真问题（机制；与 `C8` 同源） |
| P2-5 | `--no-backup` 行为错 | — | 范围外 |
| P2-6 | 两套安装器冲突 | — | 范围外 |
| P2-7 | entries 覆盖 | A | 真问题★（= `review` M14；`runner.js:776` 整体替换） |
| P2-8 | 分支名被 x-worktree 拒绝 | D | 范围外（文档不一致，D2 顺带） |
| P2-9 | 阶段卡要求调用「只手动」技能；`Skill` 工具不存在 | D | 真问题（机制；`stages/land.md` 与 `disable-model-invocation` 冲突） |
| P2-10 | 文档写了代码没读的配置 | D | 真问题（机制；`config/examples/1.5` 无消费者） |
| P2-11 | 文档之间规则不一致 | D | 真问题★（三处时限/委派/阈值冲突） |
| P2-12 | 测试质量（不可能失败的测试） | C | 真问题★（= `review` C14） |
| P2-13 | 新会话先撞已熔断主模型 | A | 真问题（机制；`session_start` 不检查熔断） |
| P2-14 | 杂项（时间戳、thinking、import 后门、E3/E4 过宽、self_check） | B/D/范围外 | 部分真问题，随对应根因顺带 |

## 3. `review-2026-10-17-v3-branch.md`

| 编号 | 问题 | 根因 | 判定 |
|---|---|---|---|
| M1 | 正常回答被判 provider 故障 | — | **已修**（`classify.ts` 只在 `stopReason==="error"` 读正文；`failover.test.ts` 有断言） |
| M2 | 无 run 会话写死 `"session"` | A | 真问题（= P0-3） |
| M3 | verify 缓存不含命令 | C | 真问题★（= P1-2） |
| M4 | done 无终态守卫 | C | 真问题★（`TERMINAL` 定义未接线；实测） |
| M5 | gate 释放 doing 占位 → 同文件两 doing | C | 真问题（机制；`xr:385` 只统计 doing，`:540-544` 改 blocked） |
| M6 | gate 只开不关 → 调度永久卡死 | C | 真问题★（= P1-8） |
| M7 | `run_dir` 不校验 id → 读写逃出仓库 | B | 真问题★（实测确认仓库外 `RUN.md` 被改写） |
| M8 | `xr import` 失败仍报成功 | C | 真问题★（`xr:680` 无 else） |
| M9 | 无文件锁 + 非原子写 | B | 真问题★（= P1-1） |
| M10 | 安装测试假通过 | C | 真问题★（本机额外发现：bash 3.2 裸 `[[ ]]` 不触发 `set -e`） |
| M11 | 看门狗工具期无限暂停 | A | 真问题★（`x-run-guard.ts:67-73` 无上限）；本轮保留“工具执行时不计 idle”，尚未补宿主级超时上限 |
| M12 | 压缩摘要空消息 | A | 真问题（= P1-5） |
| M13 | `lockedToFallback` 只置位不清零 | A | 真问题（= P1-4） |
| M14 | 两扩展 entries 互相覆盖 | A | 真问题★（= P2-7） |
| C1 | 入口同时引用两套模型 | D | 真问题★（无二选一判据） |
| C2 | `xr` 不在 PATH | D | 真问题（文档与安装不一致） |
| C3 | 提示 `/x-rail resume` 但无该命令 | D | 已修：提示改为读取 capsule 并执行 `xr status` |
| C4 | 时限/委派/失败阈值各两套 | D | 真问题★（= P2-11） |
| C5 | 文档承诺 tool 失败换模型，实现不换 | D + 删除 | 真问题（承诺与代码不一致） |
| C6 | `breaker_open` fail-open + xr 读 env | B | 真问题（= P1-7） |
| C7 | done 三标志恒 false → `continue` 分支不可达 | A + 删除 | 真问题★（`xr:465-470` = `boundaryDecision` 死代码） |
| C8 | verify 超时不杀进程组 | B | 真问题（= P2-4） |
| C9 | store 无锁、tmp 名固定、解析失败清空 | B | 真问题★（= P1-10） |
| C10 | 无 `session_shutdown` 清理定时器 | A | 真问题（机制） |
| C11 | 5 个孤儿 md | D | **删除**（或补索引） |
| C12 | install `--no-backup` / worktree 安装 | — | 范围外 |
| C13 | `subagent.ts` 无运行时消费者 | — | **删除**或降级为提示词约定 |
| C14 | 测试有效性（`re.M` 缺失、串行假并发、零覆盖） | C | 真问题（= P2-12） |
| C15 | `xr import` 非幂等 | C | 真问题（重复导入产生孤儿 run） |
| C16 | gate 去重子串匹配 + 先写后校验 | C | 真问题（机制） |
| C17 | 未知依赖报成「依赖有环」 | C | 真问题（小修，随 C 类顺带） |

## 4. `issue-2026-10-17-session-01a1499c.md`

这份报告的「问题」不是源码缺陷，而是**用一次真实运行暴露的机制缺口**。映射：

| 编号 | 问题 | 根因 | 判定 |
|---|---|---|---|
| 问题一 | 工作项通过依赖全任务独立审查，顺序倒置 | C + D | 真问题（`task_checks.py:583` 在单项验证里调全任务审查） |
| 问题二 | 审查后才采集输入摘要，旧报告绑定新版本 | C | 真问题（`task.py:298` 只比时间，不绑审查实际消费的输入） |
| 问题三 | 完成后清理破坏证据链，状态仍 `done` | C | 真问题★（实测：`task.py check` 报 `input file missing`，状态仍 `done`） |
| 问题四 | 把「分析并修复」解释为不限成本授权 | D | 真问题（`task_checks.py:231` 只检查字段非空） |
| 问题五 | 契约修订缺合法入口，需手改状态 | C | 真问题（`task.py:548`、`task_checks.py:673`、`:504`） |

## 5. 统计与结论

| 判定 | 条数 |
|---|---|
| 真问题（我复核 ★ 或机制确认） | 24（去重后） |
| 已修，不要重开 | 1（M1） |
| 两份报告重复项 | 16 组 |
| 应删除而非实现 | 6 项（`applyProbe`/探活、`new-session`、`subagent` 边界分支、三标志、`subagent.ts` 消费者、孤儿 md） |
| 存疑（本机未复现） | 3（20 并发派发、import 逃逸出仓库、扩展热加载行为） |
| 范围外（P2 杂项与环境差异） | 约 8 |

**结论**：可以修，但必须按 4 个根因修。逐条修会在 A 类上留下「两扩展继续打架」的新坑，在 C 类上留下「门能绕」的新坑。

## 6. 本次实测反例（可复跑）

```bash
# C1 verify 缓存不认命令
python3 <xr> --repo "$T" plan add U1 one --deps none --files seed.txt --verify true
python3 <xr> --repo "$T" verify U1                      # VERIFIED <hash>
python3 <xr> --repo "$T" plan add U1 one --deps none --files seed.txt --verify false
python3 <xr> --repo "$T" verify U1                      # 仍 cached，false 没跑

# C2 done 被 fail 打回
python3 <xr> --repo "$T" done U1
python3 <xr> --repo "$T" fail U1 --kind net             # ok fail U1 todo attempts=1

# B2 verify 期间 lost update
python3 <xr> --repo "$T" plan add A a --deps none --files a.txt --verify "sleep 3; true"
python3 <xr> --repo "$T" plan add B b --deps none --files b.txt --verify true
python3 <xr> --repo "$T" next                           # A doing
( python3 <xr> --repo "$T" verify A & ); sleep 0.7
python3 <xr> --repo "$T" next                           # B doing
# 等 verify 结束：B 回到 todo（被旧快照覆盖）

# B4 run_dir 逃逸
printf '%s\n' "../../../outside" > "$T/.work-docs/runs/ACTIVE"
python3 <xr> --repo "$T" status                          # 仓库外 RUN.md 被改写

# C5 gate 无出路
python3 <xr> --repo "$T" gate "要不要改接口" --default "不改" --unit G1
python3 <xr> --repo "$T" plan add G1 g2 --deps none --files a.txt --verify true   # 拒绝
python3 <xr> --repo "$T" gate resolve G1 --answer yes                              # 无此动词

# C7 假通过
bash -c 'set -e; [[ -f /nonexistent ]]; echo REACHED'   # 打印 REACHED（bash 3.2）
bash scripts/test-install-v3.sh                          # passed（断言路径不存在）

# B6 Python 3.9
/usr/bin/python3 <xr> next                               # TypeError: zip() takes no keyword arguments
```
