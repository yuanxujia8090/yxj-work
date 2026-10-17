const common = [
  '工作区 /Users/yuanxj/Documents/github/x-rail/.worktrees/v3，分支v3，基线b158f20de87d361829e9c6ed821cbc8d7b3accd0。中文报告。',
  '当前用户已授权更新方案并实现pstack参考的本地执行机制，最终由父会话提交当前分支。不推送、不全局安装、不发布、不删除、不清理、不回退用户修改。',
  '先读 plans/refactor-2026-10/pstack-local-implementation-plan.md；此文件是本轮完整规格和工作清单。所有既有阶段3修改必须保留。',
  '禁止调用x-rail相关技能执行本任务；可以阅读它们作为待修改源码。使用项目现有Python标准库、命令和测试，按计划先失败后最小实现。',
  '不要调用子代理；不要git add/commit；保留测试产物。正式输出由工具output绑定，不以提示里的文件名冒充。遇不明确常规选择直接推荐并写DECISIONS，不让用户替代可观察检查。',
  '宿主协议优先：基础设施问题保存准确错误、原运行、已有产物和恢复步骤，不绕过协议或盲目重试。'
].join('\n');
const implementation = await runs.run('implementation', {
  agent: 'worker', context: 'fresh',
  task: common + '\n你是唯一写入者，完整执行计划全部步骤直到可以独立审查。先读相关说明和代码，修正方案，再按公开CLI边界进行测试驱动实现。已有work_items.summary已经计算部分候选，不要重复造状态库。frontier必须验证传递依赖、当前证据、必要审查与资源冲突，只读输出不等于finish；通知队列和失败记录要持久化、幂等、可冷启动、不自动verified。将测试和演练设计成真实公开命令，证明失败分支不会悄悄放行。全套回归最终跑一次，定向测试随变更跑。更新计划清单和delivery，准确区分本地模拟与真实模型证据。源码check-repo对消费者忽略目录的依赖应针对性修正，不补造记录。完成返回：实现清单、来源映射、修改文件、先失败后通过证据、各检查精确结果与产物路径、未解决风险。不要停在方案或半成品，不未经证据称完成。',
  output: 'pstack-local/implementation.md'
});
emit({phase:'implementation',result:implementation});
if (!implementation.ok) return {phase:'implementation-blocked',implementation};
const reviewCommon = common + '\n只读独立审查，不修改任何文件。没有issue tracker需要使用：本地规格就是计划和当前用户已批准建议。固定比较基线为b158f20，审查命令git diff b158f20 --；还必须用git ls-files --others --exclude-standard覆盖未跟踪源码、模块、测试与文档。当前未提交因此不能只用三点比较。阅读源码、实际调用和测试，不能只信implementation报告。输出按严重程度、文件与行号、触发/影响/建议，具体证据优先；无问题如实写核对范围和限制。';
const reviews = await runs.all([
  {key:'standards',agent:'reviewer',context:'fresh',task:reviewCommon+'\n使用code-review规范轴。标准来源README.md、docs/architecture.md、docs/file-boundary.md、scripts/check-repo.sh、已有测试惯例及本地实现计划。检查单一事实源、Python3.10标准库、兼容旧记录、路径和输入校验、幂等、并发/崩溃恢复、可维护性与必要的错误处理。额外将以下视为判断性线索非硬违规：命名不清、重复逻辑、功能放错模块、成组原始字段、重复分支、散弹式修改、一个模块多职责、未要求的泛化、过长调用链、无用转发、未使用继承。工具已强制的格式不要当主要发现。保留所有具体正确性风险而非只找风格。末尾明确PASS/BLOCK及必须修复清单。',output:'pstack-local/standards-review.md'},
  {key:'spec',agent:'reviewer',context:'fresh',task:reviewCommon+'\n使用code-review需求轴。核对实施计划每条要求是否实现/部分/越界，尤其是否真实借鉴pstack统一原则按任务分流而非固定两模式或数量阈值；前沿传递依赖和过期证据是否拒绝；活动资源冲突；通知重复/冲突/冷启动/晚到版本；分类失败策略与宿主限制；逐项验证/滚动接收闭环；最终完成门不放松；安装后的模块可用。对照pstack原文poteto-mode/SKILL.md、figure-it-out/SKILL.md、playbooks/orchestrate.md和autonomous-run.md（根/Users/yuanxj/Downloads/plugins-main/pstack/skills）。严格区分上游规则和本地适配，检查文档相互矛盾与虚报验证。末尾明确PASS/BLOCK及必须修复清单。',output:'pstack-local/spec-review.md'}
]);
emit({phase:'reviews',reviews});
if (reviews.some(result => !result.ok)) return {phase:'review-infrastructure-blocked',implementation,reviews};
const closeout = await runs.run('closeout',{
  agent:'worker',context:'fresh',
  task:common+'\n你是审查后唯一写入者。先核对当前完整差异和实施者报告，再逐条独立判断以下两个审查结果，修复成立的必须项，其他建议记录原因。遵循先失败后通过，重跑受影响检查，不因无关文档变化重跑所有测试。两个审查如有BLOCK且修了代码，提供逐条定位、回归证据供父会话定向复核。更新delivery.md和实施计划勾选，诚实区分已实现/已验证/未知。最终提供未提交文件清单、检查命令/通过计数和证据引用、阻塞/限制、git diff --check。不要提交。\n实施结果：\n'+implementation.output+'\n规范审查：\n'+reviews[0].output+'\n需求审查：\n'+reviews[1].output,
  output:'pstack-local/closeout.md'
});
emit({phase:'closeout',result:closeout});
return {implementation,reviews,closeout};
