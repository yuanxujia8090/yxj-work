# 批次 B 未执行

06 的 5.10 要求在 x-rail v3 安装并验证之后运行：

```bash
bash plans/v3/evidence/skills-cleanup.sh --batch B --dry-run
bash plans/v3/evidence/skills-cleanup.sh --batch B
```

本次实现**没有运行**它。原因：脚本会改用户本机的 `~/.pi/agent/skills` 和 `~/.agents/skills`，而本环境不能碰用户的 Mac 或 `~/.pi`。用户也明确说不要运行 `--batch B`。

安装并在新会话里看到 x-rail 之后，由你在 Mac 上先 dry-run，再执行。守卫要求：x-rail 在 pi 会加载的目录、`name: x-rail`、存在 `stages/execute.md`，并且 x-handoff、x-worktree、x-self-check 都在。恢复命令由脚本写在它自己的 README 里。
