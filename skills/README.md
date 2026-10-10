# skills 目录说明

本目录包含 x-rail 独立工作流的 4 个入口技能，以及 30 个随安装一起复制、由入口按阶段主动读取或由用户主动点名调用的辅助技能。

## 入口技能

- `x-rail`：普通任务入口。它的“参考技能”一节给出阶段 → 参考文件的映射；plan 的实施计划读参考技能，轻量文档分支使用内置 `x-rail/templates/document-task.md`，不增加技能数量。
- `x-rail-long`：跨会话、外部等待或独立依赖汇总入口。多个阶段本身不触发。
- `x-handoff`：用户主动调用的交接入口。
- `x-self-check`：用户主动调用的只读会话分析入口。

## 辅助技能

30 个辅助技能 = 17 个项目级技能 + 13 个 `x-principle-*`（单条工程原则，短小、由其他技能引用）。`x-self-check` 只读分析脚本不自动读取其他技能：

- `x-how`、`x-why`、`x-blast-radius`：理解代码与判断改动影响面。
- `x-codebase-design`、`x-architect`、`x-arena`、`x-prototype`、`x-interrogate`：设计与对抗性审查。
- `x-requesting-code-review`、`x-receiving-code-review`、`x-resolving-merge-conflicts`：代码审查与冲突处理。
- `x-unslop`、`x-technical-writing`、`x-teach`、`x-typescript-best-practices`：写作与语言规范。
- `x-wizard`、`x-create-verification-skill`：人工步骤向导与项目验证技能生成。
- 13 个 `x-principle-*`：边界纪律、根因修复、最小改动、上下文窗口、类型系统等单条原则。

## 调用边界

本目录下全部 34 个技能都设置了：

```yaml
disable-model-invocation: true
```

因此模型不会因为任务内容、文件类型或错误类型自动唤起任何技能。技能只有两种加载方式：

1. 入口技能按 `x-rail` 的“参考技能”表**主动读取**对应文件（相对路径 `../<技能名>/SKILL.md`）；
2. 用户主动点名调用（`/x-<name>`）。

无论哪种方式加载，仍需遵守当前任务的 contract、`.work-docs` 文件边界、预算、熔断和验证要求。

## 阶段选择表

下表帮助用户表达目标；执行时以 [主入口路由](x-rail/SKILL.md) 为准，playbook 与参考技能路径只维护在主入口映射中。各阶段 playbook 提供“适用场景 / 输入 / 输出 / 不做什么 / 停止条件”。

| 你现在需要什么 | 阶段及可期待的结果 |
|---|---|
| 一个确定事实的简短回答 | fast-answer（快速回答），不创建任务目录 |
| 弄清现状、报错原因或恢复点 | investigate（调查），产出事实与下一步；不改代码 |
| 收集外部事实、比较选型 | research（研究），产出证据及是否继续的决策 |
| 定实现边界和方案 | design（设计），产出方案与验收；不改代码 |
| 拆实施步骤，或整理已确定材料 | plan（计划），产出可执行计划或文档 |
| 按已确认方案改文件 | exec（执行），产出变更与验证证据 |
| 修一个能观察到的错误 | bugfix（修复），产出复现、根因和修复前后证据 |
| 检查已有变更 | review（审查），产出问题和证据；只读目标文件 |
| 整理平台人工操作 | ops（操作指引），产出手册和回滚步骤 |
| 研究、设计、实施有顺序依赖 | mixed（组合任务），逐阶段通过决策门后推进 |

正式阶段启动与恢复时会显示风险、允许范围、必过验收、证据和第一步动作；验证观察面与摘要示例见 [验证说明](x-rail/playbooks/verification.md)。

## 技能元数据

每个 `skills/<name>/SKILL.md` 的头部至少包含与目录一致的 `name`、非空 `description` 和 `disable-model-invocation: true`。前两个字段用于识别职责，最后一个字段表示默认不由模型自动唤起；实际安装范围只由 `scripts/runtime-skills.txt` 决定。检查只接受单行标量并采用“不认识就拒绝”：`description` 必须能解析成非空字符串，空引号、`[]`、`false`、块标量（`|`、`>`）、纯数字、未闭合引号和 `key : value` 非规范键写法都会被拒绝，因为宿主加载器遇到它们会丢弃整个技能或读错名称。元数据检查只验证结构和边界，不根据描述自动路由或扩大调用范围。

## 安装范围

`scripts/runtime-skills.txt` 是安装清单，包含 4 个入口与全部辅助技能。它们都安装到同一个技能目录下，因此入口里的相对读取路径 `../<技能名>/SKILL.md` 在源仓库与安装目标下都成立；运行时清单是安装范围的唯一来源。

安装：`bash scripts/install.sh --dest "$HOME/.pi/agent/skills"`。`--update` 只覆盖带本仓库 `.x-rail-installed` 标记的目录。
软链安装（开发模式，直连源仓库）：`bash scripts/install.sh --dest "$HOME/.pi/agent/skills" --link`；卸载用 `--unlink`（只删指向本仓库的链接）。软链与复制模式互斥。

技能取舍先记录独立场景、加载条件和证据；三周未调用不等于无用。本轮保留全部原目录。退役只是建议，移除清单或删除目录需要另行确认。
