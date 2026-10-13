# Bugfix Playbook

<stage name="bugfix">
  <inputs>先遵守主入口的交付分流与记录强度。普通任务使用当前目标、范围、待办和实际结果；严格任务读取 contract、state 和当前阶段材料。明确只读时不落盘。</inputs>
  <procedure>## 阶段入口

普通任务按本阶段的业务步骤执行；严格任务才读取 contract/state 并保留 evidence/audit。用户授权的目标文档写指定位置。公共生命周期规则以主入口为准。

适用场景：已有可观察的错误或异常行为，需要复现、定位根因、做最小修复并回归。
输入：现象、预期与实际行为、复现条件、错误证据、相关调用方和当前基线。
输出：失败前证据、根因判断、最小修复、通过后证据和仍未覆盖的风险。
不做什么：不先改代码再找解释，不只修表面症状，不把无法复现的猜测当作已修复。
停止条件：原始复现面有失败前与通过后证据，或复现失败并明确记录阻塞与下一步。

0. Verify the working context before reproducing: execution root, branch/worktree, and whether the issue is already fixed there (`git log -S`, `git branch --contains`, current diff). Record workspace facts in the contract. If the report does not match the current baseline, stop and confirm the target workspace with the user.
1. Reproduce with expected versus actual behavior; prefer a failing command or behavioral test. 可自动化的缺陷先留下能复现根因的回归测试，确认失败原因对应目标行为，再最小修复、通过并整理；测试驱动开发的适用范围见 exec.md。已有失败日志是复现依据，不自动证明执行了完整测试驱动循环。
2. If reproduction fails, record attempted paths and stop guessing.
3. Identify the root cause and the invalid assumption with file/log evidence.
4. Make the smallest root-cause fix; label symptom-only mitigation explicitly.
5. Re-run the original reproduction surface and relevant existing checks. 问题发生在用户流程时，回归原实际入口和结果；内部函数通过不能替代页面、权限和请求链路的验收。
6. After three consecutive required verification failures, stop modifications, record strategy fingerprints and revalidate the shared assumption.
7. Preserve failing-before and passing-after evidence. The task cannot be done without both when reproducible.</procedure>
  <quality_check>复现后沿所有调用方核对根因，保存失败前与通过后证据。</quality_check>
  <exit>普通任务交付实际结果、验证与限制，不创建状态文件。严格任务核对真实证据，用 task.py finish 或 complete 提交候选；阻塞保留状态，不放宽必需验收。</exit>
</stage>
