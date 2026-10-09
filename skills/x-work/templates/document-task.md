# 轻量文档任务模板

只用于材料和目标已确定的文档整理，不用于功能设计、实施计划或代跑测试。复制下面两个 text 块分别成为任务的 contract.md、state.md；模板本身不是任务产物，不修改此文件。

替换全部双大括号变量：TASK_ID 为分配的任务目录名，OBJECTIVE 为用户目标，SOURCES 为本次固定材料路径和版本/提交（如纳入未提交差异则明确写出），DELIVERABLE 为 outputs 下文件名，NOW 为当前 UTC 时间（YYYY-MM-DDTHH:MM:SSZ）。CONTRACT_SHA256 在契约填写完毕后用 `shasum -a 256 <task-dir>/contract.md` 计算。

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
required_verification: A1 status=not_run evidence=evidence/coverage.txt
required_verification: A2 status=not_run evidence=evidence/clarity.txt
evidence:coverage|acceptance=A1|command=not_run|run_at={{NOW}}|result=not_run|last_edit_at={{NOW}}
evidence:clarity|acceptance=A2|command=not_run|run_at={{NOW}}|result=not_run|last_edit_at={{NOW}}
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
budget: 0/60
strategy_fingerprints: no-modification + no-command + no-error
updated_at: {{NOW}}
```

## 初始化与完成

1. 建立任务子目录，并建立 evidence/coverage.txt 与 evidence/clarity.txt，各写「not_run：尚未核对」，以满足证据指针存在要求；不是通过记录。
2. 填完契约，计算指纹，运行 `bash <skill-dir>/scripts/check-contract.sh <task-dir>`、`bash <skill-dir>/scripts/check-state.sh <task-dir>`。skill-dir 是本模板所在技能目录，可是源仓库路径或安装路径，不假设用户项目有 skills/。
3. 按 plan 轻量分支先写初稿，补读只服务具体缺口。更新真实工具计数、进展和 next_action；不能把模板中的 0/60 留到收尾。
4. 文档定稿后实际核对两条验收，写覆盖映射与逐条可理解性结果；记录真实 command（可以是人工核对动作描述）、run_at 与相关文档的 last_edit_at。只有核对通过才把对应 required_verification 和 evidence 的结果改为 passed，static 层标为 passed。其他未执行层保留 not_run，不宣称网站行为已验证。
5. 有关键缺口则写 blocked 及具体 blocked_by、unblock_condition、next_action；不能降低验收。全部必过项通过、完成门允许时才标 done，再运行两个校验器并更新索引。交付注明「用例已整理，测试未执行」。
