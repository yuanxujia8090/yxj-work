# Brief

子代理按表派发，不手写 workflow 语法。

```
GOAL       一句话
SCOPE      输入路径与独占输出；工作区和起点版本
CONTEXT    RUN.md#Intent、单元行、已有报告、起点版本
ACCEPTANCE 检查条件与必答问题
VERIFY     一条命令
MODEL      按当前授权和宿主能力选择
FORBIDDEN  不越范围、不推送、不覆盖用户修改
REPORT     首个结论即保存；列证据、已查和待查范围
RECOVERY   保存错误与原运行；先查询，未知不重派
STANDING   RUN.md#Standing。决策问题写 xr gate；解除门不代表故障已恢复
```
