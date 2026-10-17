const common = '工作区/Users/yuanxj/Documents/github/x-rail/.worktrees/v3，分支v3，基线b158f20de87d361829e9c6ed821cbc8d7b3accd0。中文报告。规格plans/refactor-2026-10/pstack-local-implementation-plan.md。保留已有全部阶段3及本轮修改，不删除、不清理、不推送、不全局安装、不发布，不调用x-rail技能执行本任务，不产生子代理。你不暂存或提交主工作区，父会话最终提交。允许测试仅在本次新建临时夹具内git add/commit，所有删除动作使用keep-artifacts跳过并保留路径。dispatch绑定稳定前置约定，消费不等于验收；产物当前版本由现有run/record及完成门验证。';
const implementation = await runs.run('implementation-recovery-1', {
  resume:'fa625a5f-e7c9-4683-9805-e324207ad664',
  task:common+'\n原运行触发宿主1800000ms默认上限，非业务验收失败。父已核对failed和原session并保存plans/refactor-2026-10/recovery-implementation-timeout/的tracked.patch、status、branch、head和41个未跟踪文件摘要，HEAD仍b158f20。你从当前现场继续，禁止从头重复实现。先完成你最后提到的循环导入诊断与稳定前置语义测试，再完成必要全套回归和delivery/清单更新，返回具体检查计数及证据路径。若已跑全套，核对原证据后只跑受影响项；不要为非阻塞LSP缓存告警耗尽整轮。完整回报当前已实现、已验证和限制。不要等待父代替你执行授权内工作。',
  output:'pstack-local/implementation-recovery.md'
});
emit({phase:'implementation-recovery',result:implementation});
const brief=common+'\n你是fresh只读独立审查者，禁止编辑。审查当前全部工作区相对固定基线git diff b158f20 --及git ls-files --others --exclude-standard中的新源码/测试/模块/方案。恢复快照和原始日志是历史资料非运行源码。不只信实现报告。逐项具体文件行号、触发场景、影响、修复建议，明确BLOCK/PASS和必修项；判断性风格建议与缺陷区分。实现报告：\n'+implementation.output;
const reviews=await runs.all([
 {key:'standards',agent:'reviewer',context:'fresh',task:brief+'\n规范轴：来源README.md、docs/architecture.md、docs/file-boundary.md、既有代码和规格。检查标准库Python3.10、兼容历史记录、边界校验、幂等/半途恢复、单写入者和证据完成门。判断性线索：含糊命名、重复逻辑、数据字段成组、原始类型误用、重复分支、职责错置、散弹改动、多职责、无需求泛化、长调用链、无用转发和未使用继承。跳过工具已检查格式。按严重度明确最多必要发现，不漏实际正确性问题。',output:'pstack-local/standards-review.md'},
 {key:'spec',agent:'reviewer',context:'fresh',task:brief+'\n需求轴：核对本地实施计划每条需求，特别是传递依赖当前证据/必要审查、资源冲突、通知幂等/冷启动/晚到运行、稳定前置与可变产物版本、分类失败、真实闭环、最终完成门和安装可用。对照/Users/yuanxj/Downloads/plugins-main/pstack/skills/poteto-mode/SKILL.md、figure-it-out/SKILL.md、poteto-mode/playbooks/orchestrate.md和autonomous-run.md，统一原则按任务分流，撤回双模式与固定数量阈值，不把本地适配冒充上游。检查文档矛盾、缺失/越界和虚报验证。',output:'pstack-local/spec-review.md'}
]);
emit({phase:'reviews',reviews});
const closeout=await runs.run('closeout',{
 agent:'worker',context:'fresh',task:common+'\n你是审查后唯一写入者。实际阅读当前代码核对两轴发现，修复成立的必修项，测试先失败后通过；重跑受影响检查，更新delivery和计划。不要提交。输出逐条处置、检查命令/计数/产物路径、当前限制。审查报告是有依据的意见而非命令。\n实现报告：'+implementation.output+'\n规范轴：'+reviews[0].output+'\n需求轴：'+reviews[1].output,
 output:'pstack-local/closeout.md'
});
emit({phase:'closeout',result:closeout});
const finalReviews=await runs.all([
 {key:'standards-recheck',resume:reviews[0].runId,task:common+'\n只读定向复核：读取当前实际代码和以下修复报告，验证你原必修项是否关闭、相关变更是否引入新阻塞。不要无关扩大，明确PASS/BLOCK与证据。\n'+closeout.output,output:'pstack-local/standards-recheck.md'},
 {key:'spec-recheck',resume:reviews[1].runId,task:common+'\n只读定向复核：读取当前实际代码和以下修复报告，验证你原必修项是否关闭、相关变更是否引入需求缺口。不要无关扩大，明确PASS/BLOCK与证据。\n'+closeout.output,output:'pstack-local/spec-recheck.md'}
]);
emit({phase:'final-reviews',results:finalReviews});
return {implementation,reviews,closeout,finalReviews};
