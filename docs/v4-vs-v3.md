# v3 → v4 差异与安装前须知

日期：2026-10-22。对比对象：`.worktrees/v3`（现用版本）与 `.worktrees/v4`（待安装）。
所有结论来自两边源码对比，不是设计稿推测。

## 一句话

v4 把 v3 里“任务守卫 + 模型故障切换”这一对捆绑职责拆成两个独立产物：**任务守卫默认装，模型恢复插件可选装**。
任务记账格式向后兼容 v3，但 v4 新增的列和命令在 v3 里读不了，所以**降级要靠安装备份恢复**。

## 1. 产物与加载方式

| 项 | v3 | v4 |
| --- | --- | --- |
| 扩展入口（`package.json` 的 `pi.extensions`） | `./x-failover.ts` | `./x-run-guard.ts` |
| 装进 `extensions/x-rail/` 的文件 | 含 `x-failover.ts`、`x-run-guard.ts` | 含 `x-run-guard.ts`、`host-events.ts`；**不含** `x-failover.ts` |
| 谁负责任务续跑 | `x-failover` 里的 `agent_before_settle` 调 `guardBoundary` | 守卫自己注册 `agent_before_settle` |
| 模型故障切换 | 默认开启，属于同一扩展 | 独立插件 `plugins/pi-model-recovery/`，默认不装 |
| 技能/playbook/阶段卡 | — | 与 v3 **完全相同**（`SKILL.md`、`playbooks/` 无差异） |
| 普通任务路由 | `task.py` | 仍走 `task.py`（v4 没有改这一层） |

要点：装 v4 后，**普通任务的行为和 v3 一样**；变化只发生在“用 xr 开持久 run”和“装不装模型插件”这两件事上。

## 2. 模型层：最大行为变化

| 项 | v3 | v4 插件 |
| --- | --- | --- |
| 是否默认生效 | 是，加载即接管错误重试 | 否，只有选中 `model-recovery/auto` 才生效 |
| 切换到什么模型 | 代码里写死：`openai26/gpt-6.1-sol` → `bai/deepseek-v4.1-flash` | 读你写的 `model-recovery.json` 里的链（1～3 个物理模型） |
| 状态文件 | `~/.pi/agent/state/x-failover.json`（熔断、冷却、每 run 记忆） | 无全局状态文件；分支状态由宿主保存 |
| 开关 | `/x-failover status|on|off` | 切回普通物理模型即可；`/model-recovery status` 只读查看 |
| 网关错误改写 | 有（改写错误文案帮宿主识别） | 只对 4 类已知文案追加标记，且只作用于选中虚拟模型的会话 |
| 鉴权/余额/权限错误 | 归为 E1，跳过同模型退避后**直接切到后备模型** | 明确**不换链**（`NOT_RETRYABLE`），交给宿主结束，避免绕过费用或凭据问题 |
| 隔离性 | 全局影响所有会话 | 只影响选了虚拟模型的会话；普通模型完全不受影响 |

装上 v4 扩展但**不装插件**时：模型错误行为回到 Pi 原生（内建重试），不会再自动切到 `bai/deepseek`。

## 3. 任务层：v4 新增的内容

### xr 命令

v3：`init next plan verify done fail reopen resolve status capsule decide gate import close`
v4 在此基础上新增：`inspect finish acceptance bind resume rebind receive reconcile event op guard handoff evidence list`（`take-ownership` 是 `resume` 的选项，不是独立命令）。

常用新增：

```bash
xr inspect --json                 # 唯一权威完成判断
xr finish                         # 生成收据（绑定 epoch/验收/单元/账本/审查摘要）
xr evidence record <id> --kind observation --report <仓库内报告> --record <来源>
xr evidence record <id> --kind review --report <报告> --inputs <覆盖路径> \
  --observer <独立审查会话 jsonl> --record <来源>
xr acceptance set/rebind/list
xr guard set ...                  # 守卫计数，扩展不能直写
xr handoff --reason ...           # 暂停记录，扩展不能直写
```

### 数据格式

| 文件 | v3 | v4 |
| --- | --- | --- |
| `units.tsv` | 14 列，无 `verify_kind` | 15 列，新增 `verify_kind=command|observation|review` |
| `ledger.tsv` | 9 列，无 `report_hash` | 18 列，新增 `report_hash`、`evidence_kind`、`observer`、`session_path`、`session_hash`、`input_scope`、`input_hash`、`final_hash`、`record` |
| `finish.json` | 无 | 新增收据：`acceptance_digest`、`units_digest`、`ledger_digest`、`review_digest`、`tree_digest`、`dispatch_epoch` |
| `guard.json` | 扩展直接写 | 只由 `xr guard set` 在运行锁内写 |
| `handoff.md` | 扩展直接写 | 只由 `xr handoff` 写 |

**兼容性**：v4 能读 v3 的 `units.tsv` / `ledger.tsv`（按旧表头补默认值，历史行不重写）。
**反向不行**：v3 读到 v4 的新列会判定表头错误。降级必须靠安装备份恢复，不能指望 v3 直接读。

### 完成门

v3：`done` 要求当前 VERIFIED。
v4：在同样要求之外，
- `inspect --json` 是唯一权威，收据 stale/invalid、stale 单元、未决工具副作用、pending 子代理都会让 `done_met=false`；
- `review_required: true` 时必须有当前有效的独立审查证据；
- 收据过期只能靠重新 `xr finish` 刷新（不会自动成功）；
- 任何交付变化都会让审查证据和收据一起失效。

## 4. 使用方式上要注意什么

1. **自动续跑只在有 ACTIVE run 时发生**。没有 `.work-docs/runs/ACTIVE` 的普通会话，守卫什么都不做。
2. **续跑不是无限循环**：连续 3 次语义进度不变就停，写 `handoff.md`；gate 全挡、检查器失败、未决副作用也会停。
3. **审查不能自审**：`--observer` 必须是另一个会话的 jsonl，且该会话 cwd 是当前仓库、报告文字出现在它的助手输出里。
4. **不要再手改 TSV**。v4 的 `guard.json`、`handoff.md`、`ledger.tsv` 都有锁与摘要校验，手改会让证据失效。
5. **交付变了要重新取证**：改文件后旧的 VERIFIED 会 stale，需要 `xr verify` 或重新 `xr evidence record`，再 `xr finish`。
6. **切会话不会自动接管**：新会话要显式 `xr bind`（或 `xr resume --take-ownership`）才继续；旧会话不会偷偷写。
7. **模型插件是会话级选择**：不选 `model-recovery/auto` 就完全不生效；选了之后该会话内所有请求走你的链。
8. **插件不改宿主 retry 设置**：重试次数仍由 Pi 的 `retry` 配置控制；链尾不会无限重发。

## 5. 你需要配置什么

### 装任务守卫（默认）

- **必需**：无配置文件。安装脚本负责把 `xr` 和扩展放到 `<agent-dir>`。
- **建议**：确认 `<agent-dir>/settings.json` 里 `retry.enabled` 至少开着；v4 不替你改。
- **无需**：不需要改 `models.json`、`settings.json` 的模型默认值。

### 装模型恢复插件（可选）

需要自己写一个只读配置文件（插件不会创建或修改它）：

- 路径：`<agent-dir>/model-recovery.json`，或环境变量 `PI_MODEL_RECOVERY_CONFIG` 指向别处。
- 示例（用你现有 provider）：

```json
{
  "schema": 1,
  "chain": [
    { "provider": "openai26", "model": "gpt-6.1-sol" },
    { "provider": "bai", "model": "deepseek-v4.1-flash" }
  ],
  "cooldownMs": 600000,
  "gatewayCompatibility": true
}
```

- 约束：链 1～3 个**物理**模型，去重；不能指向虚拟模型；模型必须在目录里且有凭据。
- 建议（需你自己应用）：`retry.maxRetries = 链长 - 1`、`retry.baseDelayMs = 1000`。
- 使用：把当前会话模型切到 `model-recovery/auto`；用 `/model-recovery status` 查看配置路径、有效链、当前选择。

## 6. 安装与回滚（供参考，尚未执行）

```bash
# 干跑：只打印会做什么
bash skills/x-rail/install.sh --home "$HOME" --dry-run

# 安装（会先备份旧的 extensions/x-rail 与冲突文件到 ~/.pi/agent/v3-backup-<时间>）
bash skills/x-rail/install.sh --home "$HOME"
```

安装后检查：

```bash
cat ~/.pi/agent/extensions/x-rail/package.json   # 应只有 ./x-run-guard.ts
ls ~/.pi/agent/extensions/x-rail                 # x-failover.ts 不应存在
python3 ~/.pi/agent/skills/x-rail/scripts/xr --help
```

回滚：

```bash
ls ~/.pi/agent | grep v3-backup                  # 找到备份目录
# 把备份里的 extensions/x-rail 与 skills 恢复回原位；或重新指向 v3 的 skills 软链
```

注意：回滚不会恢复 v4 写过的 run 数据到 v3 格式；v3 读不了 v4 新增列。需要保留旧 run 时，先备份 `.work-docs/runs`。

## 7. 体积上限（v4 已固化）

v3 的体积上限写在 `plans/0.0.7/体积基线与验收.md`，v4 把它变成可执行检查：`python3 scripts/check-size.py`（`scripts/check-repo.sh` 已接入）。

| 指标 | v3 基线（734f554） | v4 上限（当前实测） | 差值原因 |
| --- | ---: | ---: | --- |
| `SKILL.md` | 4,618 | 4,618 | 未改入口 |
| 五份运行说明合计 | 4,695 | 5,197 | `execute.md`、`review.md` 各加证据命令说明 |
| `stages/` + `references/` 合计 | 8,307 | 10,018 | `references/verification.md` 重写（三种证据、不可覆盖、stale） |
| 全部说明文档 | 136,819 | 138,530 | 同上，未新增说明文件 |
| 技能内代码与测试 | 253,224 | 303,066 | 只记录不设上限；新增 inspect/finish/evidence/guard/handoff/acceptance、宿主事件、收据与审查校验 |

规则与 v3 一致：以原始字节为准，不能靠合并长行或换目录规避；代码允许为必要保障增长，但要在交付里列出新增职责；阈值不通过先精简，确有例外要写明“未达目标”。

自检：`bash scripts/test-size-check.sh` 会验证“真实预算通过、故意调小的预算必须失败”。

## 8. 仍未验证（安装前请知悉）

- 安装到真实 HOME 后由 Pi 自动加载 `extensions/` 的路径（探针用显式 `--extension` 加载）。
- 真实网关错误分类、余额/鉴权分支的真实宿主行为。
- 工具副作用“只执行一次”、子代理等待、200 次续跑上限、压缩摘要实际路径。
- 审查证据不防伪造（本地单机按“有证据强于无证据”处理）。
