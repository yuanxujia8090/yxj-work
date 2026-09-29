# skills 目录说明

本目录包含 yxj-work 独立工作流的 3 个入口技能，以及 30 个随安装一起复制、由入口按阶段主动读取或由用户主动点名调用的辅助技能。

## 入口技能

- `yxj-work`：普通任务入口。它的“参考技能”一节给出阶段 → 参考文件的映射。
- `yxj-work-long`：跨阶段、跨会话或长时间任务入口。
- `yxj-work-handoff`：用户主动调用的交接入口。

## 辅助技能

30 个辅助技能 = 17 个项目级技能 + 13 个 `yxj-principle-*`（单条工程原则，短小、由其他技能引用）：

- `yxj-how`、`yxj-why`、`yxj-blast-radius`：理解代码与判断改动影响面。
- `yxj-codebase-design`、`yxj-architect`、`yxj-arena`、`yxj-prototype`、`yxj-interrogate`：设计与对抗性审查。
- `yxj-requesting-code-review`、`yxj-receiving-code-review`、`yxj-resolving-merge-conflicts`：代码审查与冲突处理。
- `yxj-unslop`、`yxj-technical-writing`、`yxj-teach`、`yxj-typescript-best-practices`：写作与语言规范。
- `yxj-wizard`、`yxj-create-verification-skill`：人工步骤向导与项目验证技能生成。
- 13 个 `yxj-principle-*`：边界纪律、根因修复、最小改动、上下文窗口、类型系统等单条原则。

## 调用边界

本目录下全部 33 个技能都设置了：

```yaml
disable-model-invocation: true
```

因此模型不会因为任务内容、文件类型或错误类型自动唤起任何技能。技能只有两种加载方式：

1. 入口技能按 `yxj-work` 的“参考技能”表**主动读取**对应文件（相对路径 `../<技能名>/SKILL.md`）；
2. 用户主动点名调用（`/yxj-<name>`）。

无论哪种方式加载，仍需遵守当前任务的 contract、`.work-docs` 文件边界、预算、熔断和验证要求。

## 安装范围

`scripts/runtime-skills.txt` 是安装清单，包含 3 个入口与全部辅助技能。它们都安装到同一个技能目录下，因此入口里的相对读取路径 `../<技能名>/SKILL.md` 在源仓库与安装目标下都成立。

安装：`bash scripts/install.sh --dest "$HOME/.pi/agent/skills"`。`--update` 只覆盖带本仓库 `.yxj-work-installed` 标记的目录。

如果确认某个技能长期不需要，从 `scripts/runtime-skills.txt` 移除对应行再删除该目录即可；门禁只校验清单里列出的目录。
