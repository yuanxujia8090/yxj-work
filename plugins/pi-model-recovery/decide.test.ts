import assert from "node:assert/strict";
import {
  CHAIN_EXHAUSTED,
  MISSING_FAILED,
  TRANSIENT_MARKER,
  decideRequest,
  emptyState,
  encodeState,
  keyOf,
  markGatewayError,
  parseConfig,
  parseState,
  type RecoveryConfig,
} from "./decide.ts";

const config: RecoveryConfig = {
  schema: 1,
  chain: [
    { provider: "local-a", model: "fixture-a" },
    { provider: "local-b", model: "fixture-b" },
    { provider: "local-c", model: "fixture-c" },
  ],
  cooldownMs: 600_000,
  gatewayCompatibility: true,
};

const cases: Array<[string, () => void]> = [];
const test = (name: string, fn: () => void) => cases.push([name, fn]);

test("配置：合法链去重且保留顺序", () => {
  const parsed = parseConfig({
    schema: 1,
    chain: [
      { provider: "a", model: "x" },
      { provider: "a", model: "x" },
      { provider: "b", model: "y" },
    ],
    cooldownMs: 1000,
  });
  assert.equal(parsed.ok, true);
  if (!parsed.ok) return;
  assert.deepEqual(parsed.config.chain.map(keyOf), ["a/x", "b/y"]);
  assert.equal(parsed.config.gatewayCompatibility, true);
});

for (const [name, raw] of [
  ["schema 不是 1", { schema: 2, chain: [{ provider: "a", model: "x" }] }],
  ["chain 不是数组", { schema: 1, chain: "a" }],
  ["chain 为空", { schema: 1, chain: [] }],
  ["chain 超过 3 个", { schema: 1, chain: [1, 2, 3, 4].map((i) => ({ provider: "p", model: `m${i}` })) }],
  ["缺 provider", { schema: 1, chain: [{ model: "x" }] }],
  ["缺 model", { schema: 1, chain: [{ provider: "a" }] }],
  ["cooldownMs 非法", { schema: 1, chain: [{ provider: "a", model: "x" }], cooldownMs: -1 }],
  ["gatewayCompatibility 非法", { schema: 1, chain: [{ provider: "a", model: "x" }], gatewayCompatibility: "yes" }],
  ["不是对象", "nope"],
] as Array<[string, unknown]>) {
  test(`配置错误：${name} 明确报错，不挑替代模型`, () => {
    const parsed = parseConfig(raw);
    assert.equal(parsed.ok, false);
    if (parsed.ok) return;
    assert.ok(parsed.error.length > 0);
  });
}

test("用户新输入：冷却已过回到主模型并清空尝试", () => {
  const state = { schema: 1 as const, activeIndex: 1, cooldownUntil: 500, attempted: ["local-a/fixture-a"] };
  const result = decideRequest({ reason: "user", config, state, now: 1000 });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 0);
  assert.deepEqual(result.state?.attempted, []);
  assert.equal(result.state?.cooldownUntil, null);
});

test("用户新输入：冷却未过期沿用当前可用后备", () => {
  const state = { schema: 1 as const, activeIndex: 1, cooldownUntil: 5000, attempted: ["local-a/fixture-a"] };
  const result = decideRequest({ reason: "user", config, state, now: 1000 });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 1);
  assert.equal(result.state?.cooldownUntil, 5000);
  assert.deepEqual(result.state?.attempted, []);
});

test("continuation 沿用最近成功模型且不写状态", () => {
  const state = { schema: 1 as const, activeIndex: 2, cooldownUntil: 9999, attempted: ["x"] };
  const result = decideRequest({ reason: "continuation", config, state, now: 1000 });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 2);
  assert.equal(result.state, undefined, "continuation 不能改写分支状态");
});

test("暂时性 retry：从失败模型之后选未尝试的模型，并设置冷却", () => {
  const result = decideRequest({
    reason: "retry",
    config,
    state: emptyState(),
    failed: { provider: "local-a", model: "fixture-a" },
    now: 1000,
  });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 1);
  assert.equal(result.state?.activeIndex, 1);
  assert.equal(result.state?.cooldownUntil, 601_000);
  assert.deepEqual(result.state?.attempted, ["local-a/fixture-a", "local-b/fixture-b"]);
});

test("暂时性 retry：不在同一故障链绕回主模型", () => {
  const state = { schema: 1 as const, activeIndex: 1, cooldownUntil: 601_000, attempted: ["local-a/fixture-a", "local-b/fixture-b"] };
  const result = decideRequest({
    reason: "retry",
    config,
    state,
    failed: { provider: "local-b", model: "fixture-b" },
    now: 2000,
  });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 2, "只能前进，不能回到已尝试的 a");
});

test("暂时性 retry：链尾耗尽返回终止错误且不再发请求", () => {
  const state = { schema: 1 as const, activeIndex: 2, cooldownUntil: 601_000, attempted: ["local-a/fixture-a", "local-b/fixture-b", "local-c/fixture-c"] };
  const result = decideRequest({
    reason: "retry",
    config,
    state,
    failed: { provider: "local-c", model: "fixture-c" },
    now: 3000,
  });
  assert.equal(result.action, "fail");
  if (result.action !== "fail") return;
  assert.equal(result.error, CHAIN_EXHAUSTED);
  assert.equal(/busy|timeout|prematurely|concurrency/i.test(result.error), false, "终止错误不能被宿主当暂时故障");
});

test("上下文溢出 retry 沿用失败模型，不消耗故障链", () => {
  const state = { schema: 1 as const, activeIndex: 1, cooldownUntil: 601_000, attempted: ["local-a/fixture-a"] };
  const result = decideRequest({
    reason: "retry",
    config,
    state,
    failed: { provider: "local-a", model: "fixture-a" },
    contextRecovery: true,
    now: 2000,
  });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 0);
  assert.equal(result.state, undefined, "上下文恢复不能改故障链状态");
});

test("retry 缺 failed：明确路由错误，不猜也不换链", () => {
  const result = decideRequest({ reason: "retry", config, state: emptyState(), now: 1000 });
  assert.equal(result.action, "fail");
  if (result.action !== "fail") return;
  assert.equal(result.error, MISSING_FAILED);
});

test("direct：优先最近成功模型，不写状态", () => {
  const result = decideRequest({ reason: "direct", config, state: { schema: 1, activeIndex: 2, cooldownUntil: 5, attempted: [] }, now: 1000 });
  assert.equal(result.action, "use");
  if (result.action !== "use") return;
  assert.equal(result.index, 2);
  assert.equal(result.state, undefined);
});

test("分支状态可 JSON 往返，坏值退回空状态", () => {
  const state = { schema: 1 as const, activeIndex: 1, cooldownUntil: 42, attempted: ["a/x"] };
  assert.deepEqual(parseState(JSON.parse(encodeState(state))), state);
  assert.deepEqual(parseState({ schema: 9 }), emptyState());
  assert.deepEqual(parseState(null), emptyState());
  assert.deepEqual(parseState({ schema: 1, activeIndex: -3 }), { schema: 1, activeIndex: 0, cooldownUntil: null, attempted: [] });
});

for (const pattern of ["账号池暂无可用账号", "gateway_concurrency_limit", "The service is busy", "Upstream stream ended prematurely"]) {
  test(`网关文案 ${pattern} 加标记并保留原文`, () => {
    const decision = markGatewayError(`upstream said: ${pattern}`, true);
    assert.equal(decision.action, "mark");
    if (decision.action !== "mark") return;
    assert.ok(decision.text.includes(pattern), "原文必须保留");
    assert.ok(decision.text.endsWith(TRANSIENT_MARKER));
  });
}

for (const [name, text] of [
  ["鉴权", "401 invalid token"],
  ["余额", "余额不足，请充值"],
  ["额度", "insufficient_quota"],
  ["权限", "permission_denied"],
  ["未知错误", "unexpected internal error"],
  ["普通回答提到 503", "文档里写了 503 是网关错误"],
] as Array<[string, string]>) {
  test(`${name}不得被标成暂时故障`, () => {
    const decision = markGatewayError(text, true);
    assert.equal(decision.action, "keep");
  });
}

test("标记不重复追加，关闭兼容时不改写", () => {
  const once = markGatewayError("The service is busy", true);
  assert.equal(once.action, "mark");
  if (once.action !== "mark") return;
  assert.equal(markGatewayError(once.text, true).action, "keep");
  assert.equal(markGatewayError("The service is busy", false).action, "keep");
});

let failed = 0;
for (const [name, fn] of cases) {
  try {
    fn();
  } catch (error) {
    failed += 1;
    console.error(`FAIL ${name}\n  ${error instanceof Error ? error.message : String(error)}`);
  }
}
if (failed > 0) {
  console.error(`model-recovery decide tests: ${failed} failed of ${cases.length}`);
  process.exit(1);
}
console.log(`model-recovery decide tests passed (${cases.length})`);
