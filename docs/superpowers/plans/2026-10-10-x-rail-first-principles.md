# x-rail 第一性原理流程收敛实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 按“结果风险和恢复需求决定流程强度”的原则，降低 x-rail 的严格流程成本，同时保留证据新鲜度、完成门和跨会话恢复能力。

**Architecture:** 保留普通任务、严格任务和长任务三层结构。普通任务不创建流程记录；严格任务保留契约、状态、证据和完成门；长任务只是严格任务的恢复属性，不新增第二套完成逻辑。本次把工具动作计数从硬门禁改为可选记录，把阶段链路和独立审查改为按未知、风险和授权触发，并收紧自动验证的输入边界。

**Tech Stack:** Python 3.10 标准库、Bash、Markdown、HTML、现有 `task.py`/`task_checks.py` 测试夹具。

## Global Constraints

- 保留当前用户已有修改和已提交基线，不回退、不覆盖无关文件。
- 不修改安装目录、用户项目或外部服务。
- 不删除数据，不执行清理，不推送。
- 不把人工、消费端或外部验收伪装成自动验收。
- 不用静态检查证明真实模型效率提升；本次不执行真实模型前后对照实验。
- 自动验证仍必须绑定输入摘要、契约版本、真实输出和证据新鲜度。
- 现有 `seal`、`check`、`complete --candidate` 兼容入口继续可用，除非测试证明它们与新语义冲突。

---

### Task 1: 移除工具计数的硬门禁

**Files:**
- Modify: `skills/x-rail/scripts/task.py`
- Modify: `scripts/test-task-checks.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/usage-guide.html`
- Modify: `skills/x-rail/SKILL.md`
- Modify: `skills/x-rail/playbooks/verification.md`

**Interfaces:**
- `task.py run` 保留 `--used` 兼容参数，但不再要求调用者提供真实工具总数；验证命令仍需显式提供 `--command`、`--expect`、`--input`。
- `task.py finish TASK_DIR` 不再要求 `--used`；可选 `--used N` 只记录执行者提供的估计值，不参与完成门。
- 状态继续使用 `budget: used/limit` 兼容旧格式；新任务使用 `budget: untracked/limit` 或等价明确值，检查器不得把执行者估计值当作真实计数。

- [x] **Step 1: 写失败测试**

在 `scripts/test-task-checks.py` 增加以下行为测试：

```python
def test_finish_does_not_require_or_trust_manual_tool_count(self):
    directory = self.fresh_task()
    self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
    self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'").returncode, 0)
    p = self.run_cli('finish', str(directory))
    self.assertEqual(p.returncode, 0, p.stderr)
    self.assertEqual(checks.check_state(directory)['status'], 'done')
    self.assertIn('budget: untracked/', (directory / 'state.md').read_text())
```

并增加：

```python
def test_optional_used_is_metadata_only(self):
    directory = self.fresh_task()
    self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
    self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'").returncode, 0)
    p = self.run_cli('finish', str(directory), '--used', '999999')
    self.assertEqual(p.returncode, 0, p.stderr)
    state = (directory / 'state.md').read_text()
    self.assertIn('tool_count_note: 999999', state)
    self.assertIn('budget: untracked/', state)
```

- [x] **Step 2: 运行失败测试**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-task-checks.py
```

预期：新增测试失败，原因是 `finish` 仍要求 `--used`，并且状态仍写入人工计数。

- [x] **Step 3: 最小实现**

在 `task.py` 中：

- 把 `finish(task_dir, used)` 改为 `finish(task_dir, used: int | None = None)`。
- `budget()` 不再接受新的人工计数作为完成依据；完成时保留原预算上限，并将未接入宿主计数的新状态写成 `budget: untracked/<limit>`。
- `--used` 改为可选兼容参数；若传入，只写入 `tool_count_note: <value>`，不改变预算状态、不解除预算暂停、不绕过预算检查。
- `run` 的 `--used` 改为可选兼容参数，若传入只写入 `tool_count_note`，不作为预算判断依据。
- 完成门继续阻止已有正式 `blocked/stopped/cancelled` 状态和旧格式实际超限状态；新未跟踪计数不制造“已计数”的假事实。

在 `task_checks.py` 中：

- 接受 `budget: untracked/<positive limit>`。
- 对 `untracked` 状态不执行基于人工计数的 `used > limit` 和 `used == limit` 判断。
- 保留 `calls_since_progress`、deadline、证据新鲜度和输入摘要检查。

- [x] **Step 4: 运行测试**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-task-checks.py
```

预期：所有任务生命周期测试通过，并明确显示测试总数和 `OK`。

- [x] **Step 5: 同步说明**

将所有示例中的强制 `--used 实际工具计数` 改成：

- 默认不传 `--used`。
- 如宿主提供真实计数，可传入并标记为观察值。
- 未接入宿主计数时，不能把 `budget` 或工具动作数当作效率证据。

- [x] **Step 6: 运行文档和结构检查**

运行：

```bash
bash scripts/check-repo.sh
python3 scripts/test-html-check.py
bash scripts/test-flow.sh
```

预期：全部返回成功。

---

### Task 2: 收敛严格任务触发规则

**Files:**
- Modify: `skills/x-rail/SKILL.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/usage-guide.html`
- Modify: `DECISIONS.md`
- Test: `scripts/test-flow.sh` 或现有流程语义检查入口

**Interfaces:**
- 记录强度判断使用两个核心问题：`failure_cost_high`（失败代价是否高）和 `recovery_or_handoff_needed`（是否需要恢复或交接）。
- 任一为真时使用严格记录；两者都为假时使用普通流程。
- 敏感动作、独立审查要求、外部等待、必需依赖汇总和用户明确要求留档继续直接触发严格记录。
- 任务名称（如“研究”“设计”）不单独触发严格记录。

- [x] **Step 1: 写失败静态检查**

在流程检查中加入最小语义断言：

```python
assert 'failure_cost_high' in core_text
assert 'recovery_or_handoff_needed' in core_text
assert '任一为真' in core_text
assert '任务名称' in core_text
```

同时断言文档包含以下反例：复杂但当前会话可完成的任务不自动进入长模式；只读分析不因复杂而创建任务记录。

- [x] **Step 2: 运行检查确认缺失**

运行：

```bash
bash scripts/test-flow.sh
```

预期：新增断言失败，确认当前入口没有明确二维判断。

- [x] **Step 3: 最小实现**

在 `SKILL.md` 的任务分流段增加二维判断表：

| 判断 | 结果 |
|---|---|
| 失败代价高，或需要恢复/交接 | 严格记录 |
| 两者都不是 | 普通流程 |

保留直接触发严格记录的敏感动作、外部等待、必需依赖汇总、独立审查和用户明确要求留档。

在 README、架构说明和 HTML 指南只保留规则解释和使用例，不复制完整契约字段。

- [x] **Step 4: 运行检查确认通过**

运行：

```bash
bash scripts/test-flow.sh
python3 scripts/test-html-check.py
```

预期：流程和 HTML 检查通过。

---

### Task 3: 弱化固定阶段链路和默认审查

**Files:**
- Modify: `skills/x-rail/SKILL.md`
- Modify: `skills/x-rail/playbooks/design.md`
- Modify: `skills/x-rail/playbooks/plan.md`
- Modify: `skills/x-rail/playbooks/exec.md`
- Modify: `skills/x-rail/playbooks/bugfix.md`
- Modify: `skills/x-rail/playbooks/review.md`
- Modify: `skills/x-rail/playbooks/mixed.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/usage-guide.html`
- Modify: `scripts/test-flow.sh`

**Interfaces:**
- 阶段仍按未知选择，不要求默认完整链路。
- 默认流程是“解决当前未知的最短路径”。
- `review` 仅在高风险、影响面大、自动覆盖不足、需求存在分歧、用户要求第二视角或关键逻辑被重新修改时触发。
- 普通小修改不因缺少 `review` 而失败。

- [x] **Step 1: 写失败静态检查**

在 `scripts/test-flow.sh` 的 Python 检查中增加：

```python
assert '最短路径' in core.find('routing').text
assert '不要求默认完整链路' in core.find('routing').text
assert '按风险触发' in core.find('routing').text
```

预期当前检查失败。

- [x] **Step 2: 运行失败检查**

运行：

```bash
bash scripts/test-flow.sh
```

预期：新断言失败。

- [x] **Step 3: 最小实现**

修改主入口和各阶段说明：

- 将开发、排查和调研链路说明为示例，不再表达为默认必经链路。
- 明确阶段选择服务于当前未知：不知道现状才调查，不知道方案才设计，不知道拆解才计划，已知改法才执行。
- 将 review 改成条件触发，并保留 `review_policy` 作为严格任务的真实约束。
- 删除各 playbook 重复的完整严格生命周期说明，只保留“普通任务直接交付；严格任务遵循主入口”的短引用。

- [x] **Step 4: 运行检查确认通过**

运行：

```bash
bash scripts/test-flow.sh
bash scripts/check-repo.sh
python3 scripts/test-html-check.py
```

预期：全部通过。

---

### Task 4: 收紧自动验证的输入边界并统一说明

**Files:**
- Modify: `skills/x-rail/scripts/task.py`
- Modify: `skills/x-rail/scripts/task_checks.py`
- Modify: `scripts/test-task-checks.py`
- Modify: `skills/x-rail/SKILL.md`
- Modify: `skills/x-rail/playbooks/verification.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/usage-guide.html`

**Interfaces:**
- 自动验证仍使用输入摘要和 SHA-256 内容摘要。
- 自动验证命令必须绑定至少一个输入文件；目录、状态、证据、审计、临时目录和符号链接继续拒绝。
- 证据文本检查只作为命令结果的一部分；文档必须说明文本包含关系不能证明完整行为。
- 对关键测试命令，说明优先使用明确退出状态、测试计数或机器可读结果。
- 不增加无法自动推断的“完整相关文件清单”承诺；文档明确输入集合由执行者声明，遗漏文件是已知限制。

- [x] **Step 1: 写失败测试**

增加：

```python
def test_run_requires_declared_input_and_documents_limit(self):
    directory = self.fresh_task()
    self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
    p = self.run_cli('run', str(directory), '--acceptance', 'A1', '--evidence', 'no-input',
                     '--workspace', str(self.root), '--expect', 'actual result',
                     '--command', "printf 'actual result\\n'")
    self.assertNotEqual(p.returncode, 0)
    self.assertIn('input', p.stderr.lower())
```

并增加文档语义断言：

```python
assert '输入集合由执行者声明' in verification_text
assert '文本包含关系不能证明完整行为' in verification_text
```

- [x] **Step 2: 运行失败测试**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-task-checks.py
python3 scripts/test-html-check.py
```

预期：新测试或文档断言失败。

- [x] **Step 3: 最小实现**

在 `task.py`：

- 保持 `--input` 为必需参数，并在参数解析和运行前给出明确错误。
- 增加对空输入集合和重复输入的明确错误信息。
- 保持输入摘要只绑定执行者声明的文件，不扩大为自动猜测。

在 `playbooks/verification.md`、README、架构说明和 HTML 指南补充：

- 输入集合由执行者声明，不能自动证明完整。
- `--expect` 是文字检查，不是行为证明。
- 机器可读测试结果优先于宽泛文字匹配。
- 自动、人工、消费端和外部验收必须分别报告。

- [x] **Step 4: 运行完整验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-task-checks.py
bash scripts/check-repo.sh
bash scripts/test-contract.sh --keep-artifacts
bash scripts/test-fixtures.sh
bash scripts/test-v2-lifecycle.sh
bash scripts/test-flow.sh
python3 scripts/test-html-check.py
bash scripts/test-skill-metadata.sh --keep-artifacts
bash scripts/test-document-template.sh
bash scripts/test-install.sh --keep-artifacts
```

预期：所有命令返回成功；测试输出显示零失败。

---

## 最终验收

- [x] 当前工作区仅包含本计划范围内的代码、测试和说明改动。
- [x] 普通任务不创建流程记录；严格任务按“高失败代价或需要恢复/交接”触发。
- [x] `task.py finish` 不要求人工工具计数；可选计数不影响完成门。
- [x] 阶段链路是按未知选择的最短路径；`review` 按风险和需求触发。
- [x] 自动验证保留真实输出、输入摘要、证据新鲜度和路径边界。
- [x] 所有完整验证命令通过。
- [x] 不执行真实模型效率对照，不声称效率已提升。
- [x] 用户要求提交时再单独提交；本计划本身不自动提交。
