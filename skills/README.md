# skills 目录说明

本目录只保留 yxj-work 独立工作流的 3 个入口技能：

- `yxj-work`：普通任务入口。
- `yxj-work-long`：跨阶段、跨会话或长时间任务入口。
- `yxj-work-handoff`：用户主动调用的交接入口。

## 调用边界

这 3 个技能都设置了：

```yaml
disable-model-invocation: true
```

它们只能由用户主动调用，不能由模型根据任务内容自动注入或自动触发。

当前仓库没有保留其他辅助技能。以后需要某个辅助技能时，由用户明确指定并重新添加；重新添加后必须保留 `disable-model-invocation: true`，并重新运行仓库检查。

## 安装范围

`scripts/runtime-skills.txt` 是安装白名单，目前只包含上述 3 个入口技能。`scripts/install.sh` 不会安装其他目录，也不会修改全局技能目录之外的用户文件。
