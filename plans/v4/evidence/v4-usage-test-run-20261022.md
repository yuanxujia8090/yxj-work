# v4 真实会话用例执行记录（2026-10-22）

对象：`.worktrees/v4`，分支 `v4`，HEAD 出发前 `52dbe8e`（本文件与用例文档随之提交）。
环境：本机 macOS，Python 3，Node（Bun 可用），Pi 1.3.0（`/Users/yuanxj/.hermes/node/bin/pi`）。
约束：只在本 worktree 与 `/tmp` 临时目录执行；未改动 `.worktrees/v3`、未安装到真实 HOME、未推送。

## 1. 取样命令（只读）

```bash
# 窗口内会话文件数
find ~/.pi/agent/sessions -name '*.jsonl' -newermt 2026-10-08 | wc -l        # 976
# 出现技能调用/任务目录/task.py 实调的主会话（脚本解析 jsonl）
# 148 次 task.py bash 调用；21 次 xr 实调
```

会话原文保留在 `~/.pi/agent/sessions/`，未复制进仓库。

## 2. 自动化回归

| 命令 | 实际输出 | 结论 |
| --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-xr.py` | `Ran 41 tests in 17.591s` + `OK` | 通过 41 项 |
| `python3 scripts/test-subagent-scenarios.py` | `passed (11 scenarios, coverage limits and launch rules)` | 通过 |
| `bash scripts/typecheck-extensions.sh` | `typecheck-extensions: passed` | 通过 |
| `node plugins/pi-model-recovery/decide.test.ts` | `model-recovery decide tests passed (35)` | 通过 35 项 |
| `node scripts/simulate-v4.mjs` | `20 passed, 0 failed`（离线，无模型调用） | 通过 |
| `node scripts/stress-guard.mjs` | `13 passed, 0 failed` | 通过 |
| `node scripts/test-model-recovery.mjs` | `passed 6 / failed 0 / requests 3`（真实模型分支 skipped） | 通过 |
| `HOST_PROBE_PI=… node scripts/test-run-lifecycle.mjs` | `passed 29 / failed 0 / requests 24` | 通过 |
| `HOST_PROBE_PI=… node scripts/test-installed-layout.mjs` | `8 passed, 0 failed`（临时 HOME `/var/folders/…/x-rail-install-DnLxnB/home`） | 通过 |
| `bash scripts/check-repo.sh` | `check-repo: passed`（内含 41 项 test-xr） | 通过 |

说明：`test-run-lifecycle.mjs` 与 `test-installed-layout.mjs` 用本地假模型；未发公网请求、未使用真实凭据。

## 3. 手工探针（TC-11 / TC-13 / TC-14）

### 3.1 跨 worktree 隔离（TC-11）

```bash
T=$(mktemp -d); cd $T; git init -q main; … ; git worktree add -q -b feat wt
cd $T/wt && XR_SESSION=s1 xr init demo          # ok init 20261022-2300-demo
cd $T/main && XR_SESSION=s1 xr inspect --json   # xr: 没有 active run。正确命令：xr init <slug>
                                                # 退出码 2
find $T -name ACTIVE                            # 只在 $T/wt/.work-docs/runs/ACTIVE
```

结论：run 归属工作区，其他目录不可见、不复用。

### 3.2 换会话写入（TC-08 补充）

```bash
env -u PI_SESSION_ID XR_SESSION=s1 xr init one                    # ok
env -u PI_SESSION_ID XR_SESSION=s2 xr next                        # xr: session 与当前绑定不一致，拒绝旧会话写入（rc=2）
env -u PI_SESSION_ID XR_SESSION=s2 xr plan add u1 …               # 同上（rc=2）
env -u PI_SESSION_ID XR_SESSION=s2 xr bind --session s2           # xr: 该运行被另一会话占用：s1。正确命令：xr resume --confirm --take-ownership --record <依据>（rc=2）
env -u PI_SESSION_ID XR_SESSION=s1 xr next                        # ok next none
```

副产物发现：不 `env -u PI_SESSION_ID` 时，`XR_SESSION` 被宿主环境 `PI_SESSION_ID` 覆盖，
绑定里记录的是 Pi 会话 UUID。行为符合“显式 --session 优先，其次宿主会话”，但文档没写优先级。

### 3.3 v4 命令形状与收口（TC-13 / TC-14）

```bash
xr evidence record u2 --kind observation --report README.md --record README.md --acceptance A1 --review
# xr: error: unrecognized arguments: --acceptance A1 --review
# xr: 参数不对。正确命令：xr init <slug> | xr plan add … | xr next | xr verify <id> | xr done <id> | …
# rc=2

xr done u2          # 未验证时：xr: 没有对应当前文件和当前验证命令的 VERIFIED ledger，不能 done。正确命令：xr verify u2
xr verify u2        # ok verify u2 VERIFIED 4d61247d70ceadd5
xr done u2          # ok done u2
xr inspect --json   # done_met=false, reasons=['验收表为空', '缺少最终集成单元']
```

补齐两步后：

```bash
xr plan add i1 "集成核对" --deps u2 --files README.md --verify true --kind integration
xr next && xr verify i1 && xr done i1
xr acceptance set A1 "README 存在且验证通过" --source README.md --units i1
xr inspect --json              # done_met=true, reasons=[]
xr finish                      # ok finish 20261022-2300-one；写出 finish.json
```

`finish.json` 实测字段：`acceptance_digest`、`units_digest`、`ledger_digest`、`review_digest`、
`tree_digest`、`dispatch_epoch=5`、`unresolved_ops=0`。

另一个失败分支：验收来源写 `session:<id>#entry:<id>` 时
`finish` 报 `cannot finish：A1 session 来源没有对应审查会话证据`（设计如此），
但提示未说明要改用仓库内文件或补审查证据。

## 4. 本轮修复

| 发现 | 处理 |
| --- | --- |
| 阶段卡没写集成单元、验收表、`xr finish` | 改 `skills/x-rail/stages/plan.md`（新增第 4 步与 quality_check）、`skills/x-rail/stages/land.md`（第 2 步收口与刷新收据） |
| 提示语缺命令形状、`plans/v4/03` 与代码读法冲突、`XR_SESSION` 优先级未写 | 只记录，不改代码（见用例文档 §4） |

## 5. 复跑（修复后）

见最终提交前的 `check-repo.sh` 与 `test-size-check.sh` 输出。
