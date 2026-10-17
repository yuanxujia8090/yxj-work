# 宿主配置补丁说明

这些文件是给用户看的片段，不是密钥，也不是会自动生效的配置。

应用到 `~/.pi/agent/models.json` 和 `~/.pi/agent/settings.json` 之前需要用户点头。本仓库的安装脚本不改这两个文件。

| 文件 | 对应 06 | 注意 |
|---|---|---|
| `1.1-bai-compat.jsonc` | P1.1 | 修 bai 的 422 `developer` |
| `1.2-retry.jsonc` | P1.2 | 必须和 x-failover 一起启用，否则重试变少又不会换模型 |
| `1.3-http-idle.jsonc` | P1.3 | A/B。对照基线：timeout 56 次，成功轮次 p99 171 秒 |
| `1.4-subagents.jsonc` | P1.4 | 键名按 04 §6。pi-subagents 0.76.1 的 schema 仍待用户对照 |
| `1.5-smart-compact.jsonc` | P1.5 | 压缩模型 bai / deepseek-v4.1-flash / low |

回滚：删掉对应字段，或恢复修改前的备份。
