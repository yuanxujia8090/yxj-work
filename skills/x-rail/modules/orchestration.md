# 按需组织与本地协调

pstack 主要来源为 poteto-mode 的按交付分流、figure-it-out 的可验证单元、autonomous-run 的完成谓词、orchestrate 的前沿与队列。云端、Cursor loop、Graphite 替换为本地工作副本、Pi 宿主和当前输入摘要。Python 只记账，不启动、唤醒、恢复或等待模型；不创建守护进程。

## 按实际需要展开

- 普通任务：结果、允许范围、完成条件明确后直接执行与验证；短小任务不建协调记录。
- 单目标持续推进：先定义可观察结束条件，逐项改动、验证与转向；未达条件继续推进，真实死路保存恢复步骤，不降低完成条件。
- 复杂任务：先写定制工作顺序与验收，先建验证，再按可独立交付的单元推进。先完成一个代表单元的实施、验证、接收，再展开同类项；已有当前同类证据可复用。
- 长期协调：确需跨会话、外部等待或持续依赖汇总时展开持久化协调循环。多个阶段或模块数量本身不要求长模式。

组织方式不新增状态，也不决定记录强度。普通清单可用于局部工作，`task.py check checklist.md` 只检查清单，不能替代证据模式的 contract/state/完成门。证据模式需恢复时沿用原任务，七状态定义见 work-items.md。

## 前沿与唯一写入者

父会话独占父记录写入；每个工作区、分支、共享文件、数据库、测试缓存和构建目录只有一个写入者。跨工作项同目录或父子路径不得并发写，glob 无法确定不相交时保守阻塞。`scope` 是同一执行工作区相对路径；脚本只使用已声明范围，不证明代理无越界行为。独立副本仍须检查测试/外部资源副作用。

`task.py frontier TASK_DIR` 从锁定契约、state 和当前证据输出 JSON。`ready` 是本次可同时派发的保守集合，按契约顺序分配冲突候选，其他项给出 `reasons/conflicts`。候选计算与 summary 共用 work_items.candidates。verified 前置递归检查关联证据、传递依赖及必要审查；blocked 只阻塞依赖它的项。整体暂停/终态及未消费的系统故障不派发。已登记未解决原运行也占资源。只读查询不写状态，不把所有 verified 当整体 done；仍须 finish/complete 的完整完成门。

## 循环

1. 核对契约、state、工作区与授权；调用 frontier 与 inbox。先接收已到原结果，不能重复启动。
2. 在宿主权限、模型、并发与成本限制内，为 ready 项明确目标、范围、验收、原运行和返回绑定。capture 本单元执行期间应保持稳定的真实前置/共享约定（排除预期修改的产物），dispatch 保存宿主原运行引用和恢复第一步；若宿主只在创建后返回运行号，创建后立即登记再交还控制权。登记本身不启动代理。update 将项设为 in_progress，owner 使用原运行号。
3. 宿主完成通知先 notify 入队，不在共享写临界区深入审查。通知可先于产物可读，不能用文件存在替代通知或验收。
4. 在安全节点 inbox，逐条核对实际产物并 consume。缺产物保持 pending；旧运行、输入/契约变化、归属不符留 rejected 事实。accepted 仅说明原结果可接收，不说明代码正确。重复 event 相同事实幂等，不同内容拒绝；重复 consume 返回原回执。
5. 成功产物按原 run/record 验证，update 原项 awaiting_verification，关联验收和必要独立审查满足后才 verified。失败先按下表处理并 update 原项 needs_fix/blocked。消费后先更新原项再重新派发，避免将未更新 pending 误当新工作。
6. 每次接收、状态变化或集成后重算 frontier，及时补位，不等待无关整批。没有独立工作就交还控制权等 Pi 原生通知。宿主协议不允许显式等待时不能轮询、切前后台或换协议。
7. 接入真实交付副本后只补受影响的组合检查，整体完成仍验证原验收、审查、依赖、授权与当前输入，再 finish。集成、提交、发布各遵当前授权；通知和提交号不授予完成。

## 公开 CLI

```bash
python3 <skill-dir>/scripts/task.py capture TASK_DIR --evidence dispatch-W1 --workspace WORKSPACE --input src/shared-interface.py
python3 <skill-dir>/scripts/task.py dispatch TASK_DIR --run HOST_RUN --item W1 --provider PI_PROVIDER --inputs evidence/dispatch-W1.inputs.json --recovery '先查询原 HOST_RUN 状态，已有输出则接收'
python3 <skill-dir>/scripts/task.py update TASK_DIR --item W1 --item-status in_progress --item-owner HOST_RUN --item-reason '已登记宿主原运行' --item-next-action '等原生完成通知'
python3 <skill-dir>/scripts/task.py notify TASK_DIR --event HOST_EVENT --run HOST_RUN --outcome success --report outputs/child-result.md --observed-at ACTUAL_TIME_WITH_TIMEZONE
python3 <skill-dir>/scripts/task.py inbox TASK_DIR
python3 <skill-dir>/scripts/task.py consume TASK_DIR --event HOST_EVENT
python3 <skill-dir>/scripts/task.py frontier TASK_DIR
```

所有新命令返回单个 JSON 对象。标识只允许字母、数字、下划线和连字符；宿主标识不符合时使用稳定映射，并在 provider/recovery 保存可追溯原引用。`--observed-at` 保存真实发生时间，不得晚于当前记录；宿主可能先完成再返回运行号，因此允许发生时间早于 dispatch 登记时间。done/cancelled 后拒绝新事件且不写记录；相同事件原内容重放仍幂等。成功 report 必须指向任务内 evidence/ 或 outputs/；失败无产物写 none。路径逃逸、软链、未知项/运行、失效输入拒绝。

`audit/coordination.json` 保存派发时 manifest（含工作区/输入摘要）、契约摘要、原运行、provider、恢复第一步、通知和消费事实。单父写入，原子替换；不是工作项当前状态库。dispatch 不覆盖原运行；只要原运行未解决，禁止另起相同工作。脚本不查询宿主，不推断存活，也不自动清锁、重试、换模型、更新 state 或验证完成。

## 失败分类与重规划

notify 的失败 `--outcome` 必须伴随准确 `--error`；已有部分产物用 `--report` 保留。分类是观察事实，`inbox.actions` 是建议，不是执行许可。

| outcome | 下一步 |
| --- | --- |
| capacity | 缩小或拆分范围，不原样重发；保留原运行与部分结果 |
| timeout | 先查询原运行，区分模型请求、工具超时与容量；范围过大缩小 |
| network | 先确认原运行，依用户重试限制与宿主协议处理暂时错误 |
| tool | 修正工具/参数；仅宿主允许时更换工具或模型 |
| acceptance | 修复实现或重规划，重新取得相关证据 |
| permission | 阻塞受影响项，等待已有权限与环境恢复 |
| infrastructure | 暂停依赖，保留准确错误、原运行、产物、已知/未知与恢复第一步 |
| unknown | 先查原运行与原因，不盲目重试 |

失败计数从持久事件按原运行去重，不因重规划/冷启动清零。它不证明已经重试，不能据此发明宿主次数；用户限制优先，已有相同命令两次/验收三次熔断保留。宿主禁换模型/重启则明确阻塞，不能绕过。

系统性权限或基础设施故障用 notify `--systemic`；立即阻止新派发，consume 前须 update 整体 blocked/stopped/cancelled 并保存解除条件。单项失败只暂停该项及依赖，独立项继续。故障恢复先核对原环境、原运行和已有产物，明确原因后恢复整体；不可查询则 unknown/blocked，不重发。

## 冷启动与暂停

按 recovery.md 读原任务，再 `inbox` 列未消费通知与 runs 中原引用，`frontier` 重算当前前沿。完成运行消费原产物；可恢复运行按宿主原生恢复；未知保留准确错误，不凭 mtime 或新运行号推断存活。输入变化只重做受影响验证，晚到结果可作参考，不能直接 verified。

暂停/压缩前用 templates/coordinator-handoff.md 保存站立约束、第一恢复动作、原运行及引用；每次宿主新建/恢复都携带当前约束与完整范围，不让摘要扩权。不复制另一份当前状态。示例演练 `python3 scripts/demo-coordination.py` 使用模拟宿主事件，真实多模型服从与跨日稳定性需另取证。

## 两类版本绑定

dispatch.inputs 仅绑定执行期间稳定的真实前置/共享约定，排除本单元预期修改的产物；consume 检查它们仍适用。若没有稳定文件前置，明确传 `--inputs none`，仅绑定锁定契约版本与原运行，不制造占位文件；不宣称已检测外部环境或未声明文件。派发 manifest 保存原事实，不是结果验收。执行者自己的 scope 文件正常变更可接收，真实前置变化则拒收。产物当前版本必须由既有 run/record 绑定目标、测试和相关材料，再以当前证据和审查核验；产物变动后旧证据不能放行后继或 finish。
