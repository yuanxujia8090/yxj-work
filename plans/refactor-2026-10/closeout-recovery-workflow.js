const brief='工作区/Users/yuanxj/Documents/github/x-rail/.worktrees/v3，分支v3，基线b158f20de87d361829e9c6ed821cbc8d7b3accd0。中文。用户已授权实现并最终父会话提交。保留全部已有修改，不删除、不清理、不推送、不全局安装，不调用x-rail技能，不产生子代理。主工作区由父最终暂存提交；测试仅允许新临时夹具add/commit并用keep-artifacts保留。';
const fixed=await runs.run('closeout-recovery-1',{
 resume:'0097b83c-0203-4328-ac05-b1baa305b26e',
 task:brief+'\n上次服务方upstream_error尚未产出修复。父已检查failed、HEAD仍b158f20，保存plans/refactor-2026-10/recovery-closeout-upstream/完整差异与76文件摘要。这是同协议恢复，从当前现场继续，不从头实施。需求审查最终output被后续简短确认覆盖，完整原报告已从原reviewer transcript恢复到plans/refactor-2026-10/validation/spec-review-full-recovered.md，请务必读；规范原报告在/Users/yuanxj/.pi/agent/sessions/--Users-yuanxj-Documents-github-x-rail-.worktrees-v3--/subagent-artifacts/outputs/7870cef2-6ce6-4e72-963a-e3c73ed29c71/pstack-local/standards-review.md。必修三类：done后新通知使公开inbox/consume/check锁死；事件真实发生早于登记时被时间下界拒收；普通清单及证据软链逃逸。前/后两项公开CLI复现证据validation/reviewer-public-counterexamples.json。采取最小根因修复，补先失败后通过测试，包括终态新通知拒绝且原事件幂等/状态字节不变、先完成后登记真实时间可接收但未来时间拒绝、清单文件/父目录/证据文件及父目录软链边界。保留finish强度，不伪造事件时间。修复后跑受影响回归与36调用演练，编译/类型、diff check，更新计划/交付。父补跑安装/元数据/模板/仓库通过证据validation/parent-additional-checks.md可引用。输出逐条修复、准确命令和计数、报告路径、限制。不要提交。',
 output:'pstack-local/closeout-recovery.md'
});
emit({phase:'fixed',result:fixed});
const reviews=await runs.all([
 {key:'standards-final',resume:'274f4dbc-4680-4c42-942c-c6a6e89514cb',task:brief+'\n只读定向复核原规范审查全部必修项和相关修改。实际读取源码/测试/日志后明确PASS或BLOCK，不只相信修复者。工具不能运行shell则读现有证据。不要发送无必要followup导致正式报告被简短确认替代；一次完整输出。\n修复报告：'+fixed.output,output:'pstack-local/standards-final.md'},
 {key:'spec-final',resume:'a325873c-0ebb-4a92-b0b2-fb5c79af5f3c',task:brief+'\n只读定向复核原需求审查全部3项必修，包含先完成后登记时间语义。你原完整报告已恢复validation/spec-review-full-recovered.md。实际读源码/测试/日志后明确PASS或BLOCK，不只信修复者。一次完整输出，后续不发送无必要确认避免覆盖正式报告。\n修复报告：'+fixed.output,output:'pstack-local/spec-final.md'}
]);
emit({phase:'final-reviews',results:reviews});
return {fixed,reviews};
