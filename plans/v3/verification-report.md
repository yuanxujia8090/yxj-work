# v3 验证记录

本环境做了脚本和类型检查，没有调用付费模型，没有改 `~/.pi`，没有跑技能清理批次 B。

## 命令

| 命令 | 结果 |
|---|---|
| `python3 scripts/test-xr.py` | 5 通过 |
| `bash scripts/test-failover.sh` | 分类、熔断、切换、切回、并发、mock26 通过 |
| `bash scripts/typecheck-extensions.sh` | 对照 `@earendil-works/pi-coding-agent@1.3.0` 通过 |
| `python3 skills/x-rail/scripts/self_check.py --root .` | 入口 4545 字节；阶段卡均低于 6 KB |
| `python3 scripts/test-v3-self-check.py` | 3 通过，含超长阶段卡失败用例 |
| `bash scripts/test-install-v3.sh` | 在临时 HOME 上 dry-run、安装、重复安装、备份通过 |
| `python3 evals/replay/harness.py` | R1–R7 的离线控制流通过；live 为待批准 |
| `python3 evals/replay/harness.py --live` | 退出码 2，未调用模型 |
| `bash scripts/check-repo.sh` 及既有 `scripts/test-*.sh` / `test-*.py` | 通过 |

## 指标

基线见 `baseline-metrics.json`（摘自 01，未重跑 mine.py）。目标对照见 06 §4。真实回放完成率、工具错误率和记账拒绝率要等用户批准 `--live` 之后才有新数字，这里不填实测。

## 独立审查

没有第二模型家族的审查。本报告只记录脚本结果。

## 残余风险

- 探活默认不做网络请求。冷却结束后，在下一个单元边界直接切回；若再次失败，按熔断留下。
- 第二兜底（beef-ds）没有启用。bai 也失败就写 handoff。
- 子进程是否加载扩展、pi-subagents 的 schema，仍待用户本机确认。
- 旧 playbook 还在，证据模式的检查器依赖它们。v3 执行路径是入口加 `stages/`。
