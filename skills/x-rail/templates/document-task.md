# 轻量文档任务模板

普通低风险文档不需要本模板：列目标、范围、依据和完成检查，直接写用户授权位置。只有用户要求严格记录或任务确需严格流程时使用本模板；已有任务保留原契约。模板适用于材料和目标已确定的整理，不用于代跑测试。

优先只复制 contract.md 块，再用 task.py start 生成状态、时间和契约摘要。下面 state.md 块保留供历史手工调用与恢复参考；模板本身不是任务产物，不修改此文件。

替换全部双大括号变量：TASK_ID 为分配的任务目录名，OBJECTIVE 为用户目标，SOURCES 为本次固定材料路径和版本/提交（如纳入未提交差异则明确写出），DELIVERABLE 为 outputs 下文件名，NOW 为当前 UTC 时间（YYYY-MM-DDTHH:MM:SSZ）。CONTRACT_SHA256 在契约填写完毕后用 `shasum -a 256 <task-dir>/contract.md` 计算。

当前用户明确不限成本时，按主入口在契约顶部加入 `cost_control: unlimited` 和 `cost_authorization: 当前用户原话及来源`，优先由 start 生成 `budget: unlimited`；手工状态也使用 unlimited。下方 6/20 次检查点和有限预算均不适用，按实际缺口推进，保留无进展与必需验收。

默认低风险仅适用于只读本地材料、产物仅留在任务目录；涉及生产、对外发布、不可逆、费用或范围变化时按入口风险规则调整，不能照抄豁免。校验器通过只证明结构，不代表文档已完成。

### contract.md

```text
# 轻量文档整理契约
task_id: {{TASK_ID}}
level: L1
task_type: plan
objective: {{OBJECTIVE}}
scope: 只读 {{SOURCES}}；仅写当前任务目录与 .work-docs/index.md；交付 outputs/{{DELIVERABLE}}
forbidden: 改项目代码和配置；搭环境、代跑测试、全量审查或发布检查；写数据库、迁移、提交、推送、发布；覆盖其他任务
risk: low
risk_reason: 本地既有材料整理，产物仅留在任务目录，无运行环境或外部状态变更
review_policy: auto
contract_revision: 1
done_when: outputs/{{DELIVERABLE}} 覆盖固定材料要求，事实有依据，步骤和预期清楚；待确认项与未执行范围明确
## Acceptance
### A1
outcome: 文档覆盖固定材料的要求，预期和事实逐项有依据；关键未决事实不伪装为已确认
verification: 对照 {{SOURCES}} 逐项记录覆盖映射与事实核对到 evidence/coverage.txt
verification_type: manual
layer: static
required: yes
### A2
outcome: 文档结构可检查，步骤和预期清楚，测试用例含场景、前置条件、操作步骤、预期结果、优先级、依据；明确测试未执行
verification: 逐条核对交付内容而非仅搜关键词，记录到 evidence/clarity.txt
verification_type: manual
layer: static
required: yes
## Unknowns
尚未确认的预期先标明；若阻塞必过验收则保持非 done。环境可运行性不属于本次验收。
## Decision Gates
action_categories: none
confirmation: exempted
confirmation_status: exempted
confirmation_reason: 用户要求本地只读整理，无费用、不可逆操作、对外发布、生产变更或范围扩大
review: auto
## Contract Changes
初始版本 1；后续实质变更按入口提升版本并记录批准来源。
```

### state.md

```text
task_id: {{TASK_ID}}
level: L1
stage: plan
status: in_progress
done_when: 文档覆盖固定材料要求，事实准确、步骤和预期清楚，范围与未执行项明确
contract_revision: 1
contract_fingerprint: {{CONTRACT_SHA256}}
evidence_schema: 2
required_verification: A1 status=not_run
required_verification: A2 status=not_run
syntax/config: not_run evidence=contract.md (文档任务不验证项目配置)
static: not_run evidence=evidence/coverage.txt,evidence/clarity.txt
runtime/local: not_run evidence=contract.md (不搭环境或执行测试)
external: not_run evidence=contract.md (不对外发布或检查服务)
consumer: not_run evidence=contract.md (用户尚未实际执行用例)
unknowns: 待读取主材料后按交付条目记录具体缺口
blocked_by: none
unblock_condition: none
next_action: 读取固定主材料，6 次资料读取检查点前形成初稿或列明具体缺口
calls_since_progress: 0
last_progress_at: {{NOW}}
budget: untracked/60
strategy_fingerprints: no-modification + no-command + no-error
updated_at: {{NOW}}
```

## 工作清单与适用边界

本模板默认整理既有材料，不是实施任务，不强制为它加工作项。复杂只读分析仍只在回复列清单；普通文档直接写授权位置。仅因条目多，不按五个、六个数量升级记录或长模式。

若严格文档确需逐项交付，在契约首个二级标题前显式加入下例，并用 start 初始化；不要把 state 片段原样混入无 schema 的模板：

```text
work_items_schema: 1
requirement:R1|outcome=读者可找到固定依据对应的完整检查步骤
work_item:W1|title=整理与核对操作文档|requirements=R1|depends=none|scope=.work-docs/tasks/{{TASK_ID}}/outputs/{{DELIVERABLE}}|required=yes|acceptances=A1,A2|skip_reason=none
```

```text
# 对应 state.md 初始片段
work_item_state:W1|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none|unblock_condition=none|reason=尚未开始|next_action=读取固定主材料
active_work_items: none
```

新严格实施必须使用该 schema；start 对 task_type=exec|bugfix 强制此字段，mixed/ops 等其他类型不由脚本猜测是否实施，但触发复杂度或范围条件的严格实施仍须显式采用，不能换类型绕过。实施不能照抄本模板“不代跑测试”的整理范围。旧记录 check/update 兼容，仅在实际需要清单时显式提升契约版本、封存并保留快照，不自动迁移或补造历史。名称或范围变化走契约变更；执行者与进度走 update --item，完整 --item-* 接口和七状态见 ../playbooks/verification.md。整体状态仍为 in_progress/done/blocked/stopped/cancelled；active_work_items 由 in_progress 项自动生成并校验一致；可选项 skipped 自动引用契约非空且非 none 的 skip_reason，保留本次 item-reason 动作说明。run/record 除原 required=yes 验收外，仅开放 schema=1 清单 work_item.acceptances 引用的 required=no 验收；未引用的可选验收仍拒绝，run 自动/record 非自动边界不变。不改变契约 required 语义，不自动升为整体必过；工作项 verified 仍须全部引用验收 passed 且证据有效，必需工作项不能 skipped，可选工作项合法 skipped 不制造 passed。工作项只引用原验收和证据，不复制 passed，不建立第二份进度。

开始、交付初稿/实现完成、新验证、审查返回、阻塞/解除、重要阶段、提交、压缩和交接前核对相关项；普通读取不逐次记账。整体 next_action 只写第一动作，某项受阻不代表全部停工；完成候选明确交付动作，不留过期等待。原运行先查再恢复。委派、接力与直接完成以 ../playbooks/exec.md 为准；调用 `/x-rail` 时当前目标范围内默认主动委派，不能把拆分或文件共享当父会话包办理由。预算依据真实信号，未知不编造；必要审查集中返回、集中修复并定向复核，不能取消必过审查。

## 初始化与完成

1. 建立任务子目录。not_run 不需要证据文件，不为存在检查制造空白通过证据。
2. 填完契约，用 `python3 <skill-dir>/scripts/task.py start <task-dir>` 生成状态并封存校验；已手写状态时保留原 seal/check 路径，不重新 start。skill-dir 是源仓库或安装技能目录，不假设用户项目有 skills/。默认严格检查；历史只读必须明确 --legacy-readonly，不能用于新完成。
3. 按 plan 轻量分支先写初稿，补读只服务具体缺口。更新进展和 next_action；未接入宿主真实计数时保留 `budget: untracked/60`，不要填写估计动作数。
4. 文档定稿后实际核对两条验收。每条 passed 指向非空证据，例如 required_verification: A1 status=passed evidence=evidence/coverage.txt。证据行例如 evidence:coverage|acceptance=A1|command=人工逐项核对固定材料与交付|run_at=实际带时区时间|result=passed|last_edit_at=相关材料最后修改时间|inputs=evidence/coverage.inputs.json|contract_revision=1。输入摘要使用 version: 1、contract_revision、绝对 workspace_root 与非空 files 列表；每项为相对 path、state: present 和原字节 sha256，删除文件用 absent。绑定材料和 outputs 文档，不绑定状态或证据自身。其他未执行层保留 not_run。
5. 有关键缺口则 blocked 并说明原因、解除条件和下一步，不能降低验收。全部必过项通过时，运行 `python3 <skill-dir>/scripts/task.py finish <task-dir>`，由脚本生成候选并完成严格检查；`--used` 仅是可选观察值，不参与完成门。原 complete --candidate 仍可用。失败保留正式状态；成功后更新索引。交付注明「用例已整理，测试未执行」。
