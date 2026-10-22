import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { assistantErrorText, classifyError } from "./classify.ts";
import { cooldownElapsed, freshBreaker, noteFailback, noteProbe, observe } from "./breaker.ts";
import { COOLDOWN_MIN_MS, HYSTERESIS_MS } from "./constants.ts";
import { planSwitch } from "./compat.ts";
import { decideFailback } from "./failback.ts";
import { concurrencyLimits, dispatchModel, reviewerFamily } from "./subagent.ts";
import { decideSwitch, freshMemory, memoryAfter } from "./switch.ts";
import { loadState, saveState } from "./store.ts";
import { boundaryDecision, compactText, nextStall, shouldContinue, watchdogDecision, watchdogDue } from "./guard-core.ts";
import { TOOL_MAX_MS, WATCHDOG_MS } from "./constants.ts";

const primary = { provider: "openai26", id: "gpt-6.1-sol" };
const fallback = { provider: "bai", id: "deepseek-v4.1-flash" };

const cases: Array<[string, { text?: string; stopReason?: string; status?: number; watchdog?: boolean }, string]> = [
  ["用户中止", { stopReason: "aborted" }, "E0"],
  ["账号池", { text: "503 账号池暂无可用账号" }, "E1"],
  ["并发上限", { text: "gateway_concurrency_limit" }, "E1"],
  ["余额", { text: "INSUFFICIENT_BALANCE" }, "E1"],
  ["额度", { text: "insufficient_quota" }, "E1"],
  ["重试延迟", { text: "Server requested 20s retry delay (max: 80s)" }, "E1"],
  ["401", { status: 401, text: "nope" }, "E1"],
  ["暂时不可用", { text: "upstream_error · The service is temporarily unavailable" }, "E2"],
  ["busy", { text: "The service is busy" }, "E2"],
  ["断流", { text: "Upstream stream ended prematurely; safe to retry" }, "E2"],
  ["断开", { text: "stream disconnected" }, "E2"],
  ["超时", { text: "Request timed out." }, "E3"],
  ["524", { text: "HTTP 524" }, "E3"],
  ["terminated", { text: "terminated" }, "E3"],
  ["连接", { text: "Connection error" }, "E3"],
  ["developer", { text: "422 unknown variant 'developer'" }, "E4"],
  ["看门狗优先于中止", { stopReason: "aborted", watchdog: true }, "E5"],
];

for (const [name, input, expected] of cases) {
  const got = classifyError(input);
  assert.equal(got.klass, expected, name);
}

// 正常完成的回答里出现错误字样（例如讨论代码里的 HTTP 401）不能当成模型故障。
const normalAnswer = { role: "assistant", stopReason: "stop", content: [{ type: "text", text: "在 fetch 里遇到 HTTP 401 时要刷新 token，Connection error 也要重试。" }] };
assert.equal(classifyError(assistantErrorText(normalAnswer)).klass, "none", "正常回答里的错误字样");
const toolTurn = { role: "assistant", stopReason: "toolUse", content: [{ type: "text", text: "Request timed out 的处理在 x.ts" }] };
assert.equal(classifyError(assistantErrorText(toolTurn)).klass, "none", "调用工具的回合里的错误字样");
const realError = { role: "assistant", stopReason: "error", errorMessage: "HTTP 401 Unauthorized", content: [] };
assert.equal(classifyError(assistantErrorText(realError)).klass, "E1", "真实错误仍按 E1");
const errorInContent = { role: "assistant", stopReason: "error", content: [{ type: "text", text: "Request timed out." }] };
assert.equal(classifyError(assistantErrorText(errorInContent)).klass, "E3", "出错回合正文里的错误仍要识别");

let breaker = freshBreaker();
breaker = observe(breaker, "E1", 0).state;
assert.equal(breaker.open, true);
assert.equal(breaker.cooldownMs, COOLDOWN_MIN_MS);
assert.equal(cooldownElapsed(breaker, COOLDOWN_MIN_MS - 1), false);
assert.equal(cooldownElapsed(breaker, COOLDOWN_MIN_MS), true);
const second = observe(noteFailback(breaker, 10), "E3", 20).state;
assert.equal(second.cooldownMs, COOLDOWN_MIN_MS * 2);
assert.equal(second.lockedToFallback, true);

let e2 = freshBreaker();
e2 = observe(e2, "E2", 0).state;
e2 = observe(e2, "E2", 1).state;
assert.equal(e2.open, false);
e2 = observe(e2, "E2", 2).state;
assert.equal(e2.open, true);

const memory = freshMemory();
const busy = decideSwitch({ classified: classifyError({ text: "The service is busy" }), current: primary, memory, disabled: false, errorText: "The service is busy" });
assert.equal(busy.action, "retry-same");
if (busy.action === "retry-same") assert.equal(busy.waitMs, 20_000);
const afterRetry = memoryAfter(memory, busy);
const busyAgain = decideSwitch({ classified: classifyError({ text: "The service is busy" }), current: primary, memory: afterRetry, disabled: false, errorText: "The service is busy" });
assert.equal(busyAgain.action, "switch");
const timed = decideSwitch({ classified: classifyError({ text: "Request timed out." }), current: primary, memory, disabled: false, errorText: "Request timed out." });
assert.equal(timed.action, "switch");
const pool = decideSwitch({ classified: classifyError({ text: "503 账号池暂无可用账号" }), current: primary, memory, disabled: false, errorText: "503 账号池暂无可用账号" });
assert.equal(pool.action, "switch");
const abort = decideSwitch({ classified: classifyError({ stopReason: "aborted" }), current: primary, memory, disabled: false, errorText: "" });
assert.equal(abort.action, "ignore");
const developer = decideSwitch({ classified: classifyError({ text: "422 unknown variant 'developer'" }), current: fallback, memory, disabled: false, errorText: "422" });
assert.equal(developer.action, "handoff");
const incompatible = planSwitch(timed, false);
assert.equal(incompatible.action, "compact-then-switch");

let probed = noteProbe(noteProbe(freshBreaker(), true), true);
assert.equal(probed.consecutiveProbeOk, 2);
probed = observe(probed, "E3", 0).state;
const readyAt = (probed.openedAt ?? 0) + probed.cooldownMs;
const back = decideFailback({
  now: readyAt,
  breaker: probed,
  policy: "auto",
  onFallback: true,
  unitBoundary: true,
  newUserTurn: false,
  contextTokens: 1000,
  probeAvailable: false,
});
assert.equal(back.action, "switch-back");
const tooBig = decideFailback({
  now: readyAt,
  breaker: probed,
  policy: "auto",
  onFallback: true,
  unitBoundary: true,
  newUserTurn: false,
  contextTokens: 250_000,
  probeAvailable: false,
});
assert.equal(tooBig.action, "compact-then-switch-back");
const locked = decideFailback({
  now: 100,
  breaker: { ...freshBreaker(), open: true, openedAt: 0, cooldownMs: 1, lockedToFallback: true },
  policy: "auto",
  onFallback: true,
  unitBoundary: true,
  newUserTurn: false,
  contextTokens: 1,
  probeAvailable: false,
});
assert.equal(locked.action, "stay");
assert.ok(HYSTERESIS_MS > 0);

assert.deepEqual(concurrencyLimits(false), { readers: 5, writers: 2, total: 5 });
assert.deepEqual(concurrencyLimits(true), { readers: 2, writers: 1, total: 2 });
assert.equal(dispatchModel(true).model, "bai/deepseek-v4.1-flash");
assert.equal(reviewerFamily(true, true).sameFamily, true);
assert.equal(reviewerFamily(false, false).model, "bai/deepseek-v4.1-flash");

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "x-failover-"));
const file = path.join(dir, "state.json");
process.env.X_FAILOVER_STATE = file;
const saved = loadState(file);
saved.disabled = true;
saveState(file, saved);
assert.equal(loadState(file).disabled, true);

const run = { id: "r", active: true, doneMet: false, allBlockedByGate: false, fingerprint: "a", continues: 0, stalledFingerprints: 0 };
assert.equal(shouldContinue({ outcome: "completed", run }).action, "continue");
assert.equal(shouldContinue({ outcome: "error", run }).action, "ignore");
assert.equal(shouldContinue({ outcome: "aborted", run }).action, "ignore");
assert.equal(shouldContinue({ outcome: "completed", run: { ...run, stalledFingerprints: 3 } }).action, "stop");
assert.equal(nextStall("a", "a", 2), 3);
assert.equal(nextStall("a", "b", 2), 0);
const capsule = "目标：x\nDone：y\n";
const summary = compactText(capsule, "s".repeat(4000));
assert.ok(summary.includes("对话要点"));
assert.ok(summary.length < capsule.length + 4000);
assert.equal(watchdogDue(0, WATCHDOG_MS, false), true);
assert.equal(watchdogDue(0, WATCHDOG_MS, true), false);

// 看门狗四态：用户中止、未到期、工具在跑（含超长工具）、任务刚更新宽限一次。
const base = { abortedByUser: false, toolAges: [] as number[], runDoingFresh: false, graceUsed: false };
assert.equal(watchdogDecision({ ...base, now: 0, lastTokenAt: 0, abortedByUser: true }), "skip");
assert.equal(watchdogDecision({ ...base, now: WATCHDOG_MS - 1, lastTokenAt: 0 }), "wait");
assert.equal(watchdogDecision({ ...base, now: WATCHDOG_MS, lastTokenAt: 0, toolAges: [1_000] }), "wait");
assert.equal(watchdogDecision({ ...base, now: WATCHDOG_MS, lastTokenAt: 0, toolAges: [TOOL_MAX_MS + 1] }), "abort");
assert.equal(watchdogDecision({ ...base, now: WATCHDOG_MS, lastTokenAt: 0, runDoingFresh: true }), "grace");
assert.equal(watchdogDecision({ ...base, now: WATCHDOG_MS, lastTokenAt: 0, runDoingFresh: true, graceUsed: true }), "abort");
assert.equal(boundaryDecision({ contextTokens: 100_000, provider: "openai26" }), "continue");
assert.equal(boundaryDecision({ contextTokens: 200_000, provider: "openai26" }), "compact");
assert.equal(boundaryDecision({ contextTokens: 300_000, provider: "bai" }), "continue");
assert.equal(boundaryDecision({ contextTokens: 400_000, provider: "bai" }), "compact");

console.log("failover tests passed");
