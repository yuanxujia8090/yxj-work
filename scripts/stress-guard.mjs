#!/usr/bin/env node
/**
 * 离线压力测试：任务守卫与模型守卫的纯决策层，不调用模型、不写运行数据。
 * 全部随机序列用固定种子，可复现。
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import {
  boundaryDecision,
  idleExpired,
  nextStall,
  shouldContinue,
} from "../skills/x-rail/extensions/guard-core.ts";
import {
  CHAIN_EXHAUSTED,
  decideRequest,
  emptyState,
  encodeState,
  isContextRecoveryStop,
  keyOf,
  markGatewayError,
  MISSING_FAILED,
  NOT_RETRYABLE,
  parseConfig,
  parseState,
  TRANSIENT_MARKER,
  HOST_RETRY_HINT,
} from "../plugins/pi-model-recovery/decide.ts";
import { IDLE_STOP_MS, MAX_CONTINUES_PER_RUN, MAX_CONTINUES_WITHOUT_PROGRESS } from "../skills/x-rail/extensions/constants.ts";

const root = path.resolve(import.meta.dirname, "..");

/** 把 JSON 解析错误包成带上下文的消息，避免静默吞掉坏数据。 */
function decodeState(json) {
  try {
    return JSON.parse(json);
  } catch (error) {
    throw new Error(`状态 JSON 解析失败：${error.message}`);
  }
}

const checks = [];
const check = (name, fn) => {
  const started = Date.now();
  try {
    const detail = fn();
    checks.push({ name, passed: true, ms: Date.now() - started, detail: detail ?? "" });
  } catch (error) {
    checks.push({ name, passed: false, ms: Date.now() - started, error: error.message });
  }
};

/** 固定种子 PRNG（mulberry32），失败可复现。 */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const config = (keys) => ({ schema: 1, chain: keys.map((key) => { const [provider, model] = key.split("/"); return { provider, model }; }), cooldownMs: 600_000, gatewayCompatibility: true });

// ---------- 任务守卫 ----------

check("shouldContinue 全矩阵：只有全部条件安全才允许继续", () => {
  const outcomes = ["completed", "aborted", "error"];
  const flags = [true, false];
  const counts = [0, 1, MAX_CONTINUES_PER_RUN - 1, MAX_CONTINUES_PER_RUN, MAX_CONTINUES_PER_RUN + 1];
  const stalls = [0, 1, MAX_CONTINUES_WITHOUT_PROGRESS - 1, MAX_CONTINUES_WITHOUT_PROGRESS, MAX_CONTINUES_WITHOUT_PROGRESS + 1];
  let cases = 0;
  let continues = 0;
  for (const outcome of outcomes) for (const active of flags) for (const doneMet of flags) for (const allBlockedByGate of flags) for (const n of counts) for (const stalled of stalls) {
    cases += 1;
    const run = { id: "r", active, doneMet, allBlockedByGate, fingerprint: "f", continues: n, stalledFingerprints: stalled };
    const decision = shouldContinue({ outcome, run });
    const safe = outcome === "completed" && active && !doneMet && !allBlockedByGate
      && n < MAX_CONTINUES_PER_RUN && stalled < MAX_CONTINUES_WITHOUT_PROGRESS;
    if (safe) {
      assert.equal(decision.action, "continue", JSON.stringify({ outcome, active, doneMet, allBlockedByGate, n, stalled }));
      assert.match(decision.message, /xr status/);
      continues += 1;
    } else {
      assert.notEqual(decision.action, "continue", JSON.stringify({ outcome, active, doneMet, allBlockedByGate, n, stalled }));
      if (decision.action === "stop") assert.equal(decision.handoff, true);
    }
  }
  return `${cases} 组合，${continues} 个继续`;
});

check("守卫续跑循环：最多 200 次，连续 3 次无进展必停", () => {
  let worst = 0;
  let stops = 0;
  for (let seed = 1; seed <= 300; seed += 1) {
    const random = rng(seed);
    let continues = 0;
    let stalled = 0;
    let previous = "";
    let fingerprint = "u0";
    let decided = "none";
    for (let step = 0; step < 1000; step += 1) {
      const decision = shouldContinue({
        outcome: "completed",
        run: { id: "r", active: true, doneMet: false, allBlockedByGate: false, fingerprint, continues, stalledFingerprints: stalled },
      });
      if (decision.action !== "continue") { decided = decision.action; break; }
      continues += 1;
      stalled = nextStall(previous, fingerprint, stalled);
      previous = fingerprint;
      // 70% 无进展，30% 有新进展；用于逼近“卡住”路径。
      if (random() > 0.7) fingerprint = `u${Math.floor(random() * 1e9)}`;
    }
    assert.ok(continues <= MAX_CONTINUES_PER_RUN, `continues=${continues} 超过上限`);
    assert.ok(stalled <= MAX_CONTINUES_WITHOUT_PROGRESS, `stalled=${stalled}`);
    worst = Math.max(worst, continues);
    stops += decided === "stop" ? 1 : 0;
  }
  return `300 轮，最长 ${worst} 次，${stops} 轮以 stop 收尾`;
});

check("nextStall：只可能是 0 或 +1，永不为负", () => {
  const random = rng(7);
  for (let i = 0; i < 50_000; i += 1) {
    const stalled = Math.floor(random() * 6);
    const previous = `p${Math.floor(random() * 5)}`;
    const current = random() < 0.5 ? previous : `q${Math.floor(random() * 5)}`;
    const next = nextStall(previous, current, stalled);
    assert.ok(next === 0 || next === stalled + 1, `${previous}/${current}/${stalled} → ${next}`);
  }
  return "50000 次";
});

check("idleExpired：阈值判定一致，用户中止永不触发", () => {
  const random = rng(11);
  for (let i = 0; i < 100_000; i += 1) {
    const idle = Math.floor(random() * 600_000) + 1;
    const lastProgressAt = Math.floor(random() * 1e9);
    const delta = Math.floor(random() * idle * 2);
    const now = lastProgressAt + delta;
    assert.equal(idleExpired({ now, lastProgressAt, abortedByUser: false, idleMs: idle }), delta >= idle);
    assert.equal(idleExpired({ now, lastProgressAt, abortedByUser: true, idleMs: idle }), false);
  }
  assert.ok(Number.isFinite(IDLE_STOP_MS) && IDLE_STOP_MS > 0, `IDLE_STOP_MS 非法：${IDLE_STOP_MS}`);
  return `IDLE_STOP_MS=${IDLE_STOP_MS}`;
});

check("boundaryDecision：上下文越大只会更倾向压缩", () => {
  const random = rng(13);
  for (let i = 0; i < 20_000; i += 1) {
    const provider = random() < 0.5 ? "openai26" : "bai";
    const a = Math.floor(random() * 1e6);
    const b = Math.floor(random() * 1e6);
    const small = Math.min(a, b);
    const large = Math.max(a, b);
    if (boundaryDecision({ contextTokens: small, provider }) === "compact") {
      assert.equal(boundaryDecision({ contextTokens: large, provider }), "compact");
    }
  }
  assert.equal(boundaryDecision({ contextTokens: null, provider: "openai26" }), "compact");
  return "20000 次";
});

// ---------- 模型守卫 ----------

check("模型换链随机游走：索引合法、不回头、必在链长内终止", () => {
  let maxRetries = 0;
  let exhausted = 0;
  for (let seed = 1; seed <= 5000; seed += 1) {
    const random = rng(seed);
    const size = 1 + Math.floor(random() * 3);
    const keys = Array.from({ length: size }, (_, index) => `p/m${index}`);
    const cfg = config(keys);
    let state = emptyState();
    let failed = keys[0];
    const attempted = new Set();
    let retries = 0;
    for (; retries < 20; retries += 1) {
      const decision = decideRequest({
        reason: "retry", config: cfg, state, now: 1_000_000,
        failed: (() => { const [provider, model] = failed.split("/"); return { provider, model }; })(),
        failedText: random() < 0.1 ? "insufficient_quota" : "429 Too Many Requests",
        contextRecovery: false,
      });
      if (decision.action === "fail") {
        assert.ok([CHAIN_EXHAUSTED, MISSING_FAILED, NOT_RETRYABLE].includes(decision.error), decision.error);
        if (decision.error === CHAIN_EXHAUSTED) exhausted += 1;
        break;
      }
      assert.equal(decision.action, "use");
      const chosen = keyOf(cfg.chain[decision.index]);
      assert.ok(decision.index >= 0 && decision.index < size, `index=${decision.index}`);
      assert.ok(!attempted.has(chosen), `绕回已尝试模型 ${chosen}`);
      attempted.add(chosen);
      failed = chosen;
      if (decision.state) state = decision.state;
    }
    assert.ok(retries <= size, `retries=${retries} > size=${size}`);
    maxRetries = Math.max(maxRetries, retries);
  }
  return `5000 链，最长 ${maxRetries} 次，${exhausted} 次链尾`;
});

check("模型换链：连续失败 N 次后一定是链尾终止，且不再有候选", () => {
  for (const size of [1, 2, 3]) {
    const keys = Array.from({ length: size }, (_, index) => `p/m${index}`);
    const cfg = config(keys);
    let state = emptyState();
    let failed = keys[0];
    let used = 0;
    for (;;) {
      const decision = decideRequest({
        reason: "retry", config: cfg, state, now: 0,
        failed: (() => { const [provider, model] = failed.split("/"); return { provider, model }; })(),
        failedText: "503", contextRecovery: false,
      });
      if (decision.action === "fail") {
        assert.equal(decision.error, CHAIN_EXHAUSTED, `size=${size}`);
        break;
      }
      used += 1;
      assert.ok(used <= size, `size=${size} 用了 ${used} 次`);
      state = decision.state;
      failed = keyOf(cfg.chain[decision.index]);
    }
    assert.equal(used, size - 1, `size=${size} 应换 ${size - 1} 次（首次失败不换）`);
  }
  return "1/2/3 个模型都走满后终止";
});

check("冷却与用户输入：冷却内保持，冷却后回主模型并清空尝试", () => {
  const cfg = config(["p/a", "p/b", "p/c"]);
  const cooled = { schema: 1, activeIndex: 2, cooldownUntil: 900, attempted: ["p/a", "p/b", "p/c"] };
  const within = decideRequest({ reason: "user", config: cfg, state: cooled, now: 800, failed: null, failedText: null, contextRecovery: false });
  assert.equal(within.index, 2);
  assert.equal(within.state.cooldownUntil, 900);
  assert.deepEqual(within.state.attempted, []);
  const after = decideRequest({ reason: "user", config: cfg, state: cooled, now: 1000, failed: null, failedText: null, contextRecovery: false });
  assert.equal(after.index, 0);
  assert.equal(after.state.cooldownUntil, null);
  return "冷却内外各一次";
});

check("状态 JSON 往返与坏值兜底", () => {
  const random = rng(17);
  for (let i = 0; i < 20_000; i += 1) {
    const state = {
      schema: 1,
      activeIndex: Math.floor(random() * 4),
      cooldownUntil: random() < 0.5 ? null : Math.floor(random() * 1e9),
      attempted: Array.from({ length: Math.floor(random() * 4) }, () => `p/m${Math.floor(random() * 4)}`),
    };
    assert.deepEqual(parseState(decodeState(encodeState(state))), state);
  }
  const garbage = [null, undefined, 0, "", "x", [], {}, { schema: 2 }, { schema: 1, activeIndex: -1 }, { schema: 1, activeIndex: 1.5 }, { schema: 1, attempted: [1, null, "ok"] }, { schema: 1, cooldownUntil: "soon" }];
  for (const value of garbage) {
    const parsed = parseState(value);
    assert.ok(Number.isInteger(parsed.activeIndex) && parsed.activeIndex >= 0, JSON.stringify(value));
    assert.ok(parsed.cooldownUntil === null || Number.isFinite(parsed.cooldownUntil), JSON.stringify(value));
    assert.ok(parsed.attempted.every((item) => typeof item === "string"), JSON.stringify(value));
  }
  return "20000 往返 + 12 坏值";
});

check("配置模糊测试：坏输入只返回错误，不抛异常", () => {
  const random = rng(19);
  let accepted = 0;
  for (let i = 0; i < 5000; i += 1) {
    const size = Math.floor(random() * 5);
    const chain = Array.from({ length: size }, () => {
      const kind = Math.floor(random() * 4);
      if (kind === 0) return null;
      if (kind === 1) return { provider: "p" };
      if (kind === 2) return { provider: "p", model: "" };
      return { provider: `p${Math.floor(random() * 2)}`, model: `m${Math.floor(random() * 2)}` };
    });
    const raw = { schema: random() < 0.9 ? 1 : 2, chain, cooldownMs: random() < 0.8 ? Math.floor(random() * 1e6) : "x", gatewayCompatibility: random() < 0.9 };
    const parsed = parseConfig(raw);
    assert.equal(typeof parsed.ok, "boolean");
    if (parsed.ok) {
      accepted += 1;
      assert.ok(parsed.config.chain.length >= 1 && parsed.config.chain.length <= 3);
      const keys = parsed.config.chain.map(keyOf);
      assert.equal(new Set(keys).size, keys.length, "接受后仍有重复模型");
      assert.ok(Number.isFinite(parsed.config.cooldownMs) && parsed.config.cooldownMs >= 0);
    }
  }
  return `5000 组，接受 ${accepted}`;
});

check("网关标记：四类幂等，其他错误一字不改", () => {
  const known = ["账号池暂无可用账号", "gateway_concurrency_limit: 12", "The service is busy", "Upstream stream ended prematurely"];
  for (const text of known) {
    const once = markGatewayError(text, true);
    assert.equal(once.action, "mark", text);
    assert.ok(once.text.startsWith(text), "必须保留原文");
    assert.ok(once.text.includes(TRANSIENT_MARKER));
    assert.ok(once.text.includes(HOST_RETRY_HINT));
    assert.equal(markGatewayError(once.text, true).action, "keep", "二次标记应幂等");
  }
  for (const text of ["401 Unauthorized", "balance insufficient", "429 Too Many Requests", "503 Service Unavailable", "unknown failure"]) {
    assert.equal(markGatewayError(text, true).action, "keep", text);
  }
  return "4 类命中，5 类不改";
});

check("上下文恢复识别：只认 length 与上下文关键词", () => {
  const yes = [{ stopReason: "length" }, { stopReason: "error", errorMessage: "maximum context length exceeded" }, { stopReason: "error", errorMessage: "prompt is too long" }];
  const no = [{ stopReason: "error", errorMessage: "The service is busy" }, { stopReason: "error", errorMessage: "insufficient_quota" }, { stopReason: "stop" }, { stopReason: "toolUse" }, null, undefined];
  for (const item of yes) assert.equal(isContextRecoveryStop(item), true, JSON.stringify(item));
  for (const item of no) assert.equal(isContextRecoveryStop(item), false, JSON.stringify(item));
  return `${yes.length} 真 / ${no.length} 假`;
});

check("环境变量非法时回退默认值（子进程）", () => {
  const code = 'import { IDLE_STOP_MS } from "./skills/x-rail/extensions/constants.ts"; console.log(IDLE_STOP_MS);';
  for (const raw of ["abc", "-1", "0", "NaN", "Infinity"]) {
    const run = spawnSync(process.execPath, ["--input-type=module", "-e", code], {
      cwd: root, encoding: "utf8", env: { ...process.env, X_RAIL_IDLE_STOP_MS: raw },
    });
    assert.equal(run.status, 0, `${raw}: ${run.stderr}`);
    const value = Number(run.stdout.trim());
    assert.ok(Number.isFinite(value) && value > 0, `X_RAIL_IDLE_STOP_MS=${raw} → ${run.stdout.trim()}`);
  }
  return "5 个非法值都回退";
});

// ---------- 汇总 ----------
const passed = checks.filter((item) => item.passed).length;
const failed = checks.length - passed;
for (const item of checks) {
  console.log(`${item.passed ? "PASS" : "FAIL"} ${item.name}（${item.ms}ms）${item.detail ? ` — ${item.detail}` : ""}${item.error ? ` — ${item.error}` : ""}`);
}
console.log(`\n${passed} passed, ${failed} failed`);
if (failed) process.exitCode = 1;
