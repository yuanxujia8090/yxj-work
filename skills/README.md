# skills 目录说明

本目录包含 yxj-work 独立工作流入口和可由用户主动调用的辅助技能。

## 工作流入口

- `yxj-work`：普通任务入口。
- `yxj-work-long`：跨阶段、跨会话或长时间任务入口。
- `yxj-work-handoff`：用户主动调用的交接入口。

## 调用边界

`skills/` 下所有技能都设置了：

```yaml
disable-model-invocation: true
```

技能只能由用户主动点名或主动调用，不能由模型根据任务内容自动注入或自动触发。`yxj-work` 和 `yxj-work-long` 不会因为任务阶段、文件类型或错误类型自动加载辅助技能。

用户主动调用辅助技能后，仍需遵守当前任务的 contract、`.work-docs` 文件边界、预算、熔断和验证要求。辅助技能不加入 `scripts/runtime-skills.txt`，不会被默认安装脚本安装。

## 安装范围

`scripts/runtime-skills.txt` 是安装白名单，目前只包含 3 个工作流入口。`scripts/install.sh` 不会安装辅助技能，也不会修改全局技能目录。

辅助技能保留在本目录，后续可以由用户主动选择使用；如果确认某个技能长期不需要，再单独删除它。
