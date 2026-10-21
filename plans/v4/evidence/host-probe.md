# Pi 本地生命周期探针

2026-10-20；Pi **1.3.0**，pi-subagents **0.78.0**。只新增探针/fixtures/本记录；不修改 xr、业务扩展或方案。

执行：`node scripts/test-run-lifecycle.mjs`。可选路径覆盖：`HOST_PROBE_PI`、`HOST_PROBE_SUBAGENTS`。无需安装依赖。每次创建独立临时目录，退出后保留全部证据，不执行清理。

最终代码连续两次运行：**13/13 assertions passed，0 failed**；每次 **4 个父 Pi 调用 + 1 个真实后台 runner，10 次本地假模型请求，8 次 loopback socket connect，0 次拒绝/远程连接**。4 个父 Pi 均 exit 0，runner 的 process terminal 也记录 exit 0。计数为探针顶层断言组，每组包含多个具体 assert，不声称只有 13 条原子断言。

- 首次最终版本：`/var/folders/8n/8hn9tlpx3j18cjtc3brs11j40000gn/T/x-rail-host-probe-9WjaBv/report.json`
- 重复验证：`/var/folders/8n/8hn9tlpx3j18cjtc3brs11j40000gn/T/x-rail-host-probe-KkQpty/report.json`

## 实际运行证据

下表相对路径均相对于第二个临时目录 `x-rail-host-probe-KkQpty`。

| 验证项 | 实际观测与断言 | 证据 |
| --- | --- | --- |
| 扩展加载 | 显式 `--extension observer.ts` 真实加载，记录 extension_loaded 与 session_start | `events.jsonl`、各 `*.command.json` |
| 正常工具 | `tool_execution_start → tool_call → execute_enter → tool_result → tool_execution_end`；result/end/transcript 的 isError=false | `order-ok.json`、`basic.stdout.jsonl` |
| 抛异常工具 | 同上顺序；抛出 `host-probe intentional failure`；result/end/transcript 的 isError=true | `order-fail.json`、`events.jsonl` |
| 执行前阻断 | `tool_execution_start → tool_call → block_decision → tool_execution_end`；**无 execute_enter、无 tool_result 扩展 hook**；仍有 isError=true 的 end 和 transcript `message_end.message.role=toolResult`，内容为阻断理由 | `order-blocked.json`、`basic.stdout.jsonl` |
| turn / settle | block 后仍有 turn_end；低层 agent_end 后出现 agent_before_settle，再到 agent_settled | `events.jsonl` |
| 新建与重启身份 | basic PID=61488、resume PID=61492，sessionId 均 `01a1595b-0681-709d-8654-e817a8d0c4cd`，sessionFile 相同；全新 Pi PID=61535 的 ID 为 `01a1595b-0826-7674-ba7c-da217bf387b5` | `events.jsonl`、`resume.command.json`、真实 `sessions/*.jsonl` |
| 重启事件 reason | `--session` 进程启动时，session_start.reason 仍为 `startup`；不能据 reason 判断是否新会话 | `events.jsonl` |
| 异步启动返回 | 父 subagent 的 `tool_result` isError=false，details.runId/asyncId 为 `e5840284-9cc3-4792-b8c1-0cbfe0213bf4`，results=[]；这时只是启动回执 | `async-launch.json` |
| 子代理实际执行 | 后台 runner PID=61621，不同于父 PID=61566；子 sessionId 为 `01a1595b-0df7-750f-bbe5-2169516a344c`；真实执行 probe_child；activeTools 恰为 `["probe_action"]` | `events.jsonl`、`requests.json` |
| 父子事件归属 | 子工具 hook 仅出现在子 PID/session；父 hook 无 probe_child；子 tool_call.parentToolCallId 缺省，**不是**父 probe_launch | `events.jsonl` |
| 异步终态与关联 | status.json.state=`complete`，steps[0].status=`complete` / exitCode=0，runId/toolCallId/sessionFile 与启动回执/子 session 一致；processTerminal.state=`observed`，runner exitCode=0 | `async-statuses.json`、下述 asyncDir/status.json |
| 事件与输出渠道 | 子事件带 `subagentSource=child` / subagentRunId / subagentStepIndex；有 subagent.run.completed 和 subagent.run.process_terminal；output-0.log 含 CHILD_DONE | `async-lifecycle-summary.json`、asyncDir/events.jsonl、asyncDir/output-0.log |
| 父完成通知与查询 | 父 JSON 流收到 `role=custom, customType=subagent-notify`，包含 CHILD_DONE 与同一个 runId；随后单次 `subagent({action:"status",id})` 成功，返回 State: complete / Process terminal: observed / 匹配 runId；默认 status 文本**不包含最终输出正文** | `async.stdout.jsonl`、`events.jsonl` 中 probe_status 的 tool_result |
| 启动不等于完成 | 父启动回执 at=1792500501650；子 agent_settled at=1792500502061，晚 411ms；终态另查状态/事件/通知 | `async-launch.json`、`events.jsonl` |

`asyncDir` 完整路径：

```text
/var/folders/8n/8hn9tlpx3j18cjtc3brs11j40000gn/T/x-rail-host-probe-KkQpty/pi-subagents-uid-501/async-subagent-runs/e5840284-9cc3-4792-b8c1-0cbfe0213bf4
```

## 隔离与出站证据

父 Pi 通过白名单 env 启动：新 HOME、PI_CODING_AGENT_DIR、session dir、cwd、TMPDIR；不传个人 auth/provider/proxy/NODE_OPTIONS。auth.json 初始化为 `{}`，结束仍为 `{}`。models.json 只有 `host-probe/local`，apiKey 是固定虚构字符串，baseUrl 为本轮 `http://127.0.0.1:<随机端口>/v1`。设置 PI_OFFLINE=1、PI_TELEMETRY=0、retry.enabled=false，subagents.modelScope 为 strict/enforce，仅允许这个本地模型。未提高并发、重试或派生数量上限。

网络 fixture 只监听 `127.0.0.1`。通过本次专有 NODE_OPTIONS preload 包装 Node Socket.connect 与 tls.connect：只放行该 IP+端口，其余 socket/TLS 同步抛错并记日志；此 preload 经真实后台 runner 继承。`network.jsonl` 记录 5 个进程都持有本次 agentDir/home/offline，所有已观测 connect 均获准且指向假模型。`requests.json` 保存全部 10 次请求，模型均为 local；没有真实凭据。

父启用 `--no-extensions --no-skills --no-prompt-templates --no-themes --no-context-files --no-mcp`，仅显式装 observer 和需要时的 pi-subagents。子 agent 显式 extensions=observer，tools=probe_action，排除 contact_supervisor/subagent/subagent_supervisor/bg_wait，allowedAgents 为空；status capabilityAudit 证明最终工具只剩 probe_action、ambient extensions 已关闭。`environment.json` 和实际 agent 配置均留在临时证据目录。未改个人配置、未软链、未安装、未调用远程模型。

## SDK 声明、源码推断、运行证据的区别

本机 Pi 根路径：`/Users/yuanxj/.hermes/node/lib/node_modules/@earendil-works/pi-coding-agent`；pi-subagents 根路径：`/Users/yuanxj/.pi/agent/npm/node_modules/pi-subagents`。

| 证据级别 | 来源 | 能支持的结论 |
| --- | --- | --- |
| SDK 声明/文档 | Pi `dist/core/extensions/types.d.ts` 的 ToolCallEvent、ToolResultEvent、ToolCallEventResult；`docs/sdk.md`、`docs/rpc.md`、`docs/models.md`、`docs/cli.md` | tool_call 可 block；事件字段与 getSessionId；agent_end 是低层结束，agent_settled 才是宿主不再续跑；本地 models.json 和显式扩展加载合法。**声明本身不证明 block 后是否有 tool_result** |
| 源码推断 | Pi `dist/core/agent-session.js` `_beforeToolCall` / `_afterToolCall`；`node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` `prepareToolCall` / `finalizeExecutedToolCall` | block 在准备阶段返回 immediate error；afterToolCall 只在已执行工具收尾调用，因此预期 block 跳过 tool_result。该推断已被本次真实运行验证 |
| 源码推断 | pi-subagents `src/runs/background/async-execution.js` runnerEnv/spawn；`src/runs/shared/child-session.js`；`src/runs/shared/child-launch.js`；`src/shared/utils.js` getAgentDir | runner 继承环境，子 SDK 会话依赖同一隔离配置；ambient extensions 由契约控制；本次显式 observer 配置实际成功。不能扩展成“所有 ambient 扩展默认一定加载”的实测结论 |
| 源码推断 | pi-subagents `src/extension/index.js` agent_end handler、`src/runs/background/auto-drain.js` | headless 宿主 agent_end 阶段 drain 后台工作并递送完成消息；本次观测确认成功通知与后续父模型 turn |
| 真实运行 | 本节列出的 report、events、父 stdout、请求日志、网络日志、status、子 transcript/输出、process terminal | 仅本次真实 Pi/本地假模型/配置组合中断言的行为；没有用 SDK 类型替代执行结果 |

## 诊断保留与限制

全部诊断目录保留，无 rm。早期失败为探针本身的差异，随后换诊断方式修正，没有把错误写成宿主缺能力：

- `x-rail-host-probe-N3T1QK`：预加载守卫误解 Node 已归一化 connect 参数，拒绝本地 socket，0 请求。读取 network/父 stdout 后修正守卫。
- `x-rail-host-probe-rJPp5o`：真实工具生命周期 7 项已通过；agent frontmatter 的 `allowedAgents: []` 被该包标量解析为字符串，精确报错 `Invalid capability ceiling allowedAgents entry '[]'.`。改为文档规定的空字段，终态 capabilityCeiling.allowedAgents=[]。
- `x-rail-host-probe-lxy6l6`：runner 已 exit 0，但假模型对子 system prompt 使用 JSON 字符串匹配，误把子请求当父请求；请求日志揭示后改为检查 system message 原文。同时按真实包状态值 `complete` 断言。
- `x-rail-host-probe-yGnR2w`：子实际执行与完成通知已成功；默认 status 不含 CHILD_DONE 正文。读取精确 statusResult，改为核对 state/runId/processTerminal，并单独验证通知与输出文件。
- `x-rail-host-probe-QKVtK2`：13/13 通过；随后增加 sessionFile/output 关联断言，再连续两次通过。

未验证：外部杀进程/崩溃/中断/timeout/terminate 分支；压缩失败与 willRetry；大仓库 xr inspect 或 capsule 耗时；交互式 /new、resume/fork/reload；foreground 子会话；ambient 扩展默认继承行为；真实模型完成率/费用。该探针不实现 v4 业务逻辑，也不证明宿主有事务性工具语义。临时目录为本机保留证据，OS 日后可能清理；需要长期归档时复制到经授权位置。

对 v4 下一步的已证实约束：block 不能只依赖 tool_result hook 收尾；子代理启动 op_result 不能代表子任务终态；父子归属应使用各自 sessionId 与独立 runId/status/通知关联，不能把 parentToolCallId 当跨进程父子关联键。规格调整交由父会话决定。

补充回归：`node scripts/test-mock26.mjs` passed；`bash scripts/check-repo.sh` passed（其中 test-xr 为 13 tests OK）；`git diff --check` passed；暂存区为空。
