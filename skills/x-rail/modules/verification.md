# 验证规则

本模块定义证据模式的验证机制；旧“严格任务”字段保持兼容。

---

## 验证原则

普通任务依实际完成条件运行必要检查，并核对预期结果、说明未验证项；工具成功不是任务成功。

严格任务的检查命令默认严格模式，历史只能 `--legacy-readonly`，不得用缺字段降级。

`evidence_schema: 2` 必需。

---

## 证据绑定

`run/record` 除原 `required=yes` 外，仅对 `work_items_schema=1` 清单中被 `work_item.acceptances` 引用的 `required=no` 可选验收开放登记，未引用的可选验收仍拒绝。

`run` 自动、`record` 非自动及契约要求的审查边界不变。

不改变契约 `required` 语义，不自动升为整体必过；引用可选验收的工作项要 `verified`，仍须该验收 `passed` 且证据有效。

必需工作项不能 `skipped`，可选工作项合法 `skipped` 不制造 `passed`。

每条 `passed` 验收绑定唯一非空证据、契约版本、command、run_at、last_edit_at、inputs。

命令只是数据。证据任务内路径；输入摘要按相关文件原字节 SHA-256，不纳入状态或证据自身。时间带时区解析成 UTC 比较。审查也绑定当前输入。

调用 `task.py complete` 提交候选，失败保留正式状态与索引。

---

## 五种观察面

像检查网页一样：组件能编译、按钮能点击、用户能走完流程，是不同证据。

**代码层、接口层、流程层、运行层、交付层**表示观察对象，不是新的任务等级，也不是 `layer` 的新枚举。

现有 `layer` 仍只有 `syntax/config|static|runtime/local|external|consumer`；按实际运行环境选择，同一观察面可以跨层。

每条新增或调整的 Acceptance 都写清"观察对象、预期结果、验证动作"；使用现有 `outcome` 和 `verification` 字段即可，不增加必填字段。

evidence 记录实际观察结果、失败输出、时间和限制，并沿用 acceptance 编号绑定。

**仅运行命令而没有核对预期结果不能作为通过证据。**

---

## 验证类型

`verification_type` 表示由谁/怎样验证：

- `automatic`：自动命令或断言
- `manual`：人工逐项核对
- `consumer`：最终用户或下游系统实际消费产物
- `external`：验证依赖外部服务或权限

它与环境层 `layer` 分开：
- 例如自动调用外部服务为 `automatic + external`
- 本地用户流程可以为 `consumer + runtime/local`

---

## 证据状态

- 证据无法取得时写 `not_run`
- 实际运行未达到预期写 `failed`
- 被权限或依赖卡住写 `blocked`

**required 条目不能凭较低层证据放行，不为凑完成降低 required 条目。**

---

## 五类观察面详解

### 1. 代码层（Code Layer）

**观察对象**：源代码的静态结构和语法正确性

**典型验证**：
- 编译通过（TypeScript/Go/Rust）
- 语法检查通过（ESLint/Pylint）
- 类型检查通过（mypy/TypeScript）
- 导入路径有效

**示例**：
```yaml
acceptance:
  - id: A1
    outcome: "TypeScript编译无错误"
    verification: "pnpm typecheck"
    layer: static
    verification_type: automatic
    required: yes
```

### 2. 接口层（Interface Layer）

**观察对象**：API、函数签名、契约的正确性

**典型验证**：
- 单元测试通过
- API响应符合schema
- 函数返回正确类型
- Mock调用正确

**示例**：
```yaml
acceptance:
  - id: A2
    outcome: "getUserById返回User对象"
    verification: "pytest tests/test_user_api.py::test_get_user_by_id"
    layer: runtime/local
    verification_type: automatic
    required: yes
```

### 3. 流程层（Flow Layer）

**观察对象**：业务流程的完整性和正确性

**典型验证**：
- 集成测试通过
- 端到端测试通过
- 状态机转换正确
- 多步骤流程完整

**示例**：
```yaml
acceptance:
  - id: A3
    outcome: "用户注册到登录完整流程通过"
    verification: "playwright test tests/e2e/auth-flow.spec.ts"
    layer: runtime/local
    verification_type: automatic
    required: yes
```

### 4. 运行层（Runtime Layer）

**观察对象**：实际运行环境中的行为

**典型验证**：
- 服务启动成功
- 健康检查通过
- 日志无错误
- 性能指标符合预期

**示例**：
```yaml
acceptance:
  - id: A4
    outcome: "服务在端口3000启动且/health返回200"
    verification: "curl http://localhost:3000/health"
    layer: runtime/local
    verification_type: automatic
    required: yes
```

### 5. 交付层（Delivery Layer）

**观察对象**：最终交付物的可用性

**典型验证**：
- 用户手动验证
- 客户验收
- 生产环境验证
- 实际用户反馈

**示例**：
```yaml
acceptance:
  - id: A5
    outcome: "用户能在生产环境完成支付流程"
    verification: "手动测试：登录→选商品→支付→确认订单"
    layer: external
    verification_type: consumer
    required: yes
```

---

## 证据示例

### 自动验证证据

```yaml
evidence:
  - acceptance_id: A1
    result: passed
    command: "pnpm typecheck"
    exit_code: 0
    output_summary: "0 errors"
    evidence_path: "evidence/a1-typecheck.txt"
    run_at: "2026-10-17T01:45:00Z"
    contract_version: 1
    inputs:
      - path: "src/auth.ts"
        sha256: "abc123..."
```

### 手动验证证据

```yaml
evidence:
  - acceptance_id: A5
    result: passed
    verification_method: "手动测试"
    observed: "用户在生产环境完成支付，订单号#12345已生成"
    evidence_path: "evidence/a5-manual-test.md"
    run_at: "2026-10-17T02:00:00Z"
    contract_version: 1
```

---

## 常见错误

### ❌ 错误：只运行命令，不核对结果

```yaml
acceptance:
  - id: A1
    outcome: "测试通过"
    verification: "pytest tests/"  # 没说预期结果是什么
```

### ✓ 正确：明确预期结果

```yaml
acceptance:
  - id: A1
    outcome: "所有单元测试通过，覆盖率>80%"
    verification: "pytest tests/ --cov --cov-report=term"
```

### ❌ 错误：用低层证据替代高层验收

```yaml
# 用户要求"支付流程能用"，但只提供了单元测试证据
acceptance:
  - id: A1
    outcome: "支付流程能用"
    verification: "pytest tests/unit/test_payment.py"  # 只测了函数，没测流程
    required: yes
```

### ✓ 正确：按观察面选择验证

```yaml
acceptance:
  - id: A1
    outcome: "支付API单元测试通过"
    verification: "pytest tests/unit/test_payment.py"
    layer: runtime/local
    required: yes
  - id: A2
    outcome: "用户能完成支付流程"
    verification: "playwright test tests/e2e/payment-flow.spec.ts"
    layer: runtime/local
    required: yes
```

---

## 何时读取本模块

- 写契约时：定义 acceptances
- 执行验证时：运行 task.py run 或 record
- 审查证据时：核对证据是否绑定到正确的观察面
