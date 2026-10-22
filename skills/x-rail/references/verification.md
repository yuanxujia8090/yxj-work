# 验证

完成只看两件事：RUN.md 的 Done 判据，以及 ledger 里对应当前输入和最终产物的 VERIFIED 记录。

证据三种，全部写同一个 `ledger.tsv`，区别只在 `verify_kind`：

1. `command`：`xr verify <id>` 跑该单元的 verify_cmd，把退出码、命令摘要和报告摘要写入 ledger。
2. `observation`：没有可执行命令的文档/研究/人工核对。先 `xr plan add <id> ... --verify-kind observation`（不给 `--verify`），完成后 `xr evidence record <id> --kind observation --report <仓库内报告> --record <来源>`。
3. `review`：独立审查。`--verify-kind review`，并用 `xr evidence record <id> --kind review --report <报告> --inputs <审查覆盖的路径> --observer <审查会话 jsonl> --record <来源>`。审查会话必须属于当前工作区、不是实现会话，且报告文字要出现在该会话的助手输出里。

规则：

- 报告会被复制进 `notes/evidence-<id>-<kind>-<序号>.md`，只增不改；同名目标已存在就失败。
- 报告必须非空且位于仓库内；运行目录里的原始文件不能直接当报告。
- 没有 VERIFIED 时 `xr done <id>` 拒绝，并给下一步命令。
- 输入、产物、报告或审查会话任一变化，旧证据变 stale，`inspect` 会把该单元列为 stale 并阻止完成；重跑 `xr verify` 或重新 `xr evidence record` 追加新记录，旧记录不删。
- RUN.md 写 `review_required: true` 时，没有当前有效的 review 证据就阻止完成。
