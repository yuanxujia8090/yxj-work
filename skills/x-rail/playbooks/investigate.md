# Investigate Playbook

<stage name="investigate">
  <inputs>当前用户授权、contract、state、当前阶段材料。明确只读时不落盘。输入与约束先核对。</inputs>
  <procedure>## 阶段入口

适用场景：需要确认现状、定位原因、恢复工作，或问题还不能稳定复现。
输入：用户描述、现象、报错、相关任务记录和可定位的代码/配置范围。
输出：事实、推断、未知、证据指针、影响的验证层，以及可执行的下一步。
不做什么：不在根因和复现证据不足时修改代码，不把猜测写成结论，不代替 bugfix 阶段实施修复。
停止条件：问题已被证据回答并可进入 bugfix/review，或证据不足而应标记 blocked 并写明解除条件。

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/x-rail/scripts/check-contract.sh &lt;task-dir&gt;` before broad exploration. For an existing task, read task state, contract and recent evidence first. If a model request times out, record a recovery summary in `audit/` before continuing.
2. State the observable question and done_when; identify the smallest read or runtime check that can answer it.
3. Narrow files, configuration, services and versions before running commands.
4. Record findings as fact, inference or unknown with evidence pointers.
5. Report the affected verification layer: `syntax/config`, `static`, `runtime/local`, `external`, or `consumer`.
6. Do not create a formal output unless the contract requires one; durable command results belong in `evidence/` and decisions in `audit/`.
7. If evidence cannot resolve the question, set `blocked` with attempted paths, shared assumption, unblock condition and next action.</procedure>
  <quality_check>每次读取缩小未知；不能用环境扫描代替目标产出。</quality_check>
  <exit>输出新结论或目标产物版本、证据与未覆盖项。严格 check；候选完成走 task.py complete。阻塞保留状态，不放宽必需验收。</exit>
</stage>
