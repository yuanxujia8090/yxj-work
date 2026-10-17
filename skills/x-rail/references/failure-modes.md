# 失败类型

`xr fail <id> --kind` 只接受这些值：

| kind | 之后 |
|---|---|
| cap | 单元标成 abandoned，拆小后用 xr plan add 新单元。不 resume |
| net | 同模型再试 1 次（attempts < 2 时回到 todo） |
| tool | 换模型后再试 1 次 |
| logic / verify | 不重试同一做法，直接 abandoned，重新规划 |
| unknown | 再试 1 次，第二次 abandoned |

同一模型的 provider 自动重试另计，最多 1 次，然后交给 x-failover。
