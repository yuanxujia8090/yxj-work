# v4：任务守卫与模型恢复插件

日期：2026-10-22。两个产物互相独立：可以只装一个。

## 产物一：x-rail 任务守卫

入口：`skills/x-rail/SKILL.md`、`skills/x-rail/extensions/x-run-guard.ts`、`skills/x-rail/scripts/xr`。

运行记录在项目目录下 `.work-docs/runs/<run-id>/`：

| 文件 | 作用 |
| --- | --- |
| `RUN.md` | 目标、验收、`dispatch_epoch`、`review_required` |
| `units.tsv` | 工作项；`verify_kind` 为 `command`/`observation`/`review` |
| `ledger.tsv` | 每次证据尝试一行，只增不改 |
| `acceptance.tsv` | 验收表，`units` 列引用工作项 |
| `events.jsonl` | 宿主事件（意图、结果、接收、续跑、暂停） |
| `binding.json` | 会话、generation、lease |
| `guard.json` | 续跑计数与阻塞指纹 |
| `finish.json` | 收口收据，绑定各摘要 |
| `notes/` | 证据报告、审查会话副本、子代理回执 |

### 证据三种，同一个账本

```bash
xr plan add u1 "改接口" --deps none --files src/api.ts --verify "pnpm test api"     # command
xr plan add u2 "核对文档" --deps none --files docs/a.md --verify-kind observation
xr plan add u3 "独立审查" --deps u2 --files docs/a.md --kind review --verify-kind review

xr verify u1                     # 跑命令，写 ledger
xr evidence record u2 --kind observation --report docs/a.md --record host:manual
xr evidence record u3 --kind review --report reviews/a.md --inputs docs/a.md \
  --observer /path/to/review-session.jsonl --record host:independent-review
```

规则：

- 报告必须非空且在仓库内；运行目录里的原始文件不能直接当报告。
- 副本以独占创建写到 `notes/`，重名失败，不覆盖旧报告。
- 审查会话必须属于当前仓库、不是实现会话，报告文字要出现在该会话的助手输出里。
- 输入、产物、报告或审查会话任一变化，旧证据变 stale，`inspect` 列出该单元并阻止完成。
- `review_required: true` 时缺当前有效审查即阻止完成；`finish.json` 绑定 `review_digest`。
- `xr verify` 不能用于 observation/review 单元；也不允许用 `--verify "true"` 冒充测试。

### 完成判定与暂停

`xr inspect --json` 是唯一权威。未决工具副作用、pending 子代理、坏事件尾、stale 单元、收据 stale/invalid 都会让 `done_met=false`。

守卫在 `agent_before_settle` 决定继续或停止：

- 有可做工作且没有未决副作用 → 注入一次续接，带运行目录和当前工作项。
- 连续 3 次语义进度相同 → 写 `handoff.md` 并停。
- 连续 `IDLE_STOP_MS`（默认 10 分钟，可用 `X_RAIL_IDLE_STOP_MS` 覆盖）没有任何产出 → 停并写 handoff。产出包括流事件、工具活动、单元表/账本变化；不按任务总时长或单工具总时长判断。
- 剩余工作被 gate 挡住、检查器无结果、handoff 写不进去 → 停。
- 等待活跃子代理 → 只提示，不重复派发，不计数。
- 中止（Esc/abort）或切会话 → 不续跑；新会话必须重新 `xr bind` 才接管。

## 产物二：模型恢复插件（可选）

目录：`plugins/pi-model-recovery/`，入口 `index.ts`。不导入 x-rail，不读任务状态。

配置默认读 `<agent-dir>/model-recovery.json`，可用 `PI_MODEL_RECOVERY_CONFIG` 指定；插件只读，不创建也不修改。

```json
{
  "schema": 1,
  "chain": [
    { "provider": "bai", "model": "deepseek-v4.1-flash" },
    { "provider": "openai26", "model": "gpt-6.1-sol" }
  ],
  "cooldownMs": 600000,
  "gatewayCompatibility": true
}
```

- 链 1～3 个物理模型，去重；不能指到另一个虚拟模型。
- 配置缺失或无效：不注册虚拟模型，普通物理模型不受影响；`/model-recovery status` 显示原因。
- 只有用户主动选择 `model-recovery/auto` 才生效；不改默认模型，不改宿主 retry 设置。
- 选模型：用户新输入在冷却过期后回主模型；continuation 沿用最近成功模型；retry 只前进不绕回；上下文溢出沿用失败模型；direct 不写状态。
- 网关兼容只标记 4 类已知暂时文案（`账号池暂无可用账号`、`gateway_concurrency_limit`、`The service is busy`、`Upstream stream ended prematurely`），保留原文、幂等；鉴权/余额/权限/未知一律不改写。
- 链尾给终止错误，不再发物理请求。

## 打包

```bash
bash scripts/package-v4.sh --dest <新目录> --dry-run
bash scripts/package-v4.sh --dest <新目录>
```

- 两个产物各一份 `manifest.json`：入口、来源提交、树摘要、文件清单。
- 拒绝导出到已存在目录；不覆盖、不备份。
- 包内不含 `node_modules`、`plans/`、`.work-docs`、凭据、`.pyc` 与旧 failover 入口。
- 不执行安装，不改真实 HOME 或软链。

## 实测过的宿主事实（Pi 1.3.0）

- 多个扩展的 `agent_before_settle` 结果链式覆盖：后运行的 `entries` 会整体替换前者，所以续跑只能有一个责任方。
- `AgentSettledEvent` 只有 `aborted`；边界 outcome 必须取 `agent_before_settle` 当时保存的值。
- `new_session` 会重置扩展模块状态，且不重发 `session_start`；必须在 `agent_start` 核对会话身份。
- 别的扩展抢先 `block` 时，本扩展的 `tool_call` 不再执行；工具未执行时 `tool_execution_end` 不带 `durationMs`。
