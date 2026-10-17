# 验证（v3）

完成只看两件事：RUN.md 的 Done 判据，以及 ledger 里对应当前 tree hash 的 VERIFIED。

1. `xr verify <id>` 跑该单元的 verify_cmd，把退出码和证据路径写入 ledger。
2. 没有 VERIFIED 时，`xr done <id>` 会拒绝，并给出 `xr verify <id>`。
3. Land 还要在最终树上跑全量测试或 typecheck。高风险单元再调用 Skill 工具 code-review。

证据模式的观察面、七状态和 task.py 参数见 `playbooks/verification.md`。那份说明不参与 v3 的完成判定。
