#!/usr/bin/env node
/**
 * v4 离线模拟：不启动 Pi、不请求任何模型。
 *
 * 三段：
 *  1) 任务闭环：用临时 git 仓库 + xr 走一遍 init → 计划 → 验证 → 完成 → 收据 → 篡改 → 审查 → 过期
 *  2) 守卫决策：直接调用 guard-core 的纯函数，覆盖继续/停止/等待/中止
 *  3) 打包与安装预演：导出到临时目录，并在临时 HOME 跑安装（不碰真实 HOME）
 */
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import {
  boundaryDecision,
  compactText,
  nextStall,
  renderHandoff,
  shouldContinue,
  watchdogDue,
} from "../skills/x-rail/extensions/guard-core.ts";
import { MAX_CONTINUES_PER_RUN, MAX_CONTINUES_WITHOUT_PROGRESS } from "../skills/x-rail/extensions/constants.ts";

const root = path.resolve(import.meta.dirname, "..");
const xr = path.join(root, "skills/x-rail/scripts/xr");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "v4-sim-"));
const results = [];
const record = (section, name, passed, detail = "") => results.push({ section, name, passed, detail });

function step(section, name, fn) {
  try {
    const detail = fn();
    record(section, name, true, detail ? String(detail) : "");
  } catch (error) {
    record(section, name, false, error instanceof Error ? error.message : String(error));
  }
}

const repo = path.join(work, "repo");
fs.mkdirSync(repo, { recursive: true });
const session = randomUUID();
const env = { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PI_SESSION_ID: "" };
const runXr = (args, opts = {}) => spawnSync("python3", [xr, ...args], { cwd: opts.cwd ?? repo, encoding: "utf8", env: { ...env, ...opts.env } });
const xrOk = (args, opts) => {
  const result = runXr(args, opts);
  assert.equal(result.status, 0, `${args.join(" ")} → ${result.status}: ${result.stdout}${result.stderr}`);
  return result;
};
function parseJson(text, label) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${label} 不是合法 JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

const xrJson = (args) => parseJson(xrOk([...args, "--json"]).stdout, args.join(" "));

fs.writeFileSync(path.join(repo, "README.md"), "sim\n");
fs.writeFileSync(path.join(repo, "note.md"), "pending\n");
execFileSync("git", ["init", "-q"], { cwd: repo });
execFileSync("git", ["add", "-A"], { cwd: repo });
execFileSync("git", ["-c", "user.email=sim@example.com", "-c", "user.name=sim", "commit", "-qm", "init"], { cwd: repo });

const runDirName = () => fs.readFileSync(path.join(repo, ".work-docs/runs/ACTIVE"), "utf8").trim();
const runDir = () => path.join(repo, ".work-docs/runs", runDirName());

// ---------- 1. 任务闭环 ----------
step("task", "init 绑定会话", () => {
  xrOk(["init", "sim", "--session", session]);
  return runDirName();
});

step("task", "计划：集成单元 + 验收表", () => {
  xrOk(["--session", session, "plan", "add", "i", "集成", "--deps", "none", "--files", "README.md", "--verify", "true", "--kind", "integration"]);
  xrOk(["--session", session, "acceptance", "set", "A1", "集成通过", "--source", "README.md", "--units", "i"]);
  return "planned";
});

step("task", "未验证时不得完成", () => {
  xrOk(["--session", session, "next"]);
  const done = runXr(["--session", session, "done", "i"]);
  assert.notEqual(done.status, 0, "done 在没有 VERIFIED 时不该成功");
  return done.stdout.trim().split("\n")[0];
});

step("task", "验证 → 完成 → inspect 满足", () => {
  xrOk(["--session", session, "verify", "i"]);
  xrOk(["--session", session, "done", "i"]);
  const snap = xrJson(["--session", session, "inspect"]);
  assert.equal(snap.done_met, true, JSON.stringify(snap.reasons));
  return "done_met=true";
});

step("task", "人工观察证据：重复登记被拒", () => {
  fs.writeFileSync(path.join(repo, "obs.md"), "verbatim\n");
  xrOk(["--session", session, "plan", "add", "o", "观察", "--deps", "i", "--files", "obs.md", "--verify-kind", "observation"]);
  xrOk(["--session", session, "next"]);
  xrOk(["--session", session, "evidence", "record", "o", "--kind", "observation", "--report", "obs.md", "--record", "sim:manual"]);
  const again = runXr(["--session", session, "evidence", "record", "o", "--kind", "observation", "--report", "obs.md", "--record", "sim:manual"]);
  assert.notEqual(again.status, 0, "同一版本重复登记应被拒绝");
  xrOk(["--session", session, "done", "o"]);
  return "duplicate rejected";
});

step("task", "审查证据：自审被拒，独立会话通过", () => {
  fs.writeFileSync(path.join(repo, "review.md"), "looks good\n");
  xrOk(["--session", session, "plan", "add", "r", "审查", "--deps", "o", "--files", "review.md", "--kind", "review", "--verify-kind", "review"]);
  xrOk(["--session", session, "next"]);
  const reviewer = path.join(repo, "reviewer.jsonl");
  fs.writeFileSync(reviewer, [
    JSON.stringify({ type: "session", id: session, cwd: fs.realpathSync(repo) }),
    JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "looks good" }] } }),
  ].join("\n") + "\n");
  const self = runXr(["--session", session, "evidence", "record", "r", "--kind", "review", "--report", "review.md", "--observer", reviewer, "--record", "sim:self"]);
  assert.notEqual(self.status, 0, "实现会话不能自审");
  fs.writeFileSync(reviewer, [
    JSON.stringify({ type: "session", id: "reviewer-sim", cwd: fs.realpathSync(repo) }),
    JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "looks good" }] } }),
  ].join("\n") + "\n");
  xrOk(["--session", session, "evidence", "record", "r", "--kind", "review", "--report", "review.md", "--inputs", "review.md,obs.md", "--observer", reviewer, "--record", "sim:review"]);
  xrOk(["--session", session, "done", "r"]);
  return "self rejected, independent accepted";
});

step("task", "finish 生成收据且 inspect 认可", () => {
  xrOk(["--session", session, "finish"]);
  const snap = xrJson(["--session", session, "inspect"]);
  assert.equal(snap.receipt_status, "valid");
  assert.equal(snap.done_met, true);
  return "receipt=valid";
});

step("task", "篡改证据后收据 stale 且阻止完成", () => {
  const rows = fs.readFileSync(path.join(runDir(), "ledger.tsv"), "utf8").split("\n").map((line) => line.split("\t"));
  const header = rows[0];
  const evidenceIndex = header.indexOf("evidence_path");
  const row = rows.find((item) => item[0] === "i" && item[header.indexOf("verdict")] === "VERIFIED");
  assert.ok(row, "找不到 VERIFIED 行");
  fs.writeFileSync(path.join(runDir(), row[evidenceIndex]), "tampered\n");
  const snap = xrJson(["--session", session, "inspect"]);
  assert.equal(snap.done_met, false);
  assert.ok(snap.reasons.some((reason) => reason.startsWith("stale:") || reason.startsWith("receipt:")), JSON.stringify(snap.reasons));
  return snap.reasons.join(",");
});

step("task", "重跑验证后收据仍 stale，重新 finish 才恢复", () => {
  xrOk(["--session", session, "verify", "i"]);
  const stale = xrJson(["--session", session, "inspect"]);
  assert.equal(stale.receipt_status, "stale", JSON.stringify(stale));
  assert.equal(stale.done_met, false);
  xrOk(["--session", session, "finish"]);
  const snap = xrJson(["--session", session, "inspect"]);
  assert.equal(snap.done_met, true, JSON.stringify(snap.reasons));
  assert.equal(snap.receipt_status, "valid");
  return "stale→finish→valid";
});

step("task", "交付变化后审查证据变 stale", () => {
  fs.writeFileSync(path.join(repo, "obs.md"), "changed\n");
  const snap = xrJson(["--session", session, "inspect"]);
  assert.equal(snap.done_met, false);
  assert.ok(snap.reasons.some((reason) => /stale|审查/.test(reason)), JSON.stringify(snap.reasons));
  return snap.reasons.join(",");
});

// ---------- 2. 守卫决策（纯函数，无模型） ----------
step("guard", "中止 / 错误 / 无运行 / 已完成：不继续", () => {
  const run = { id: "x", active: true, doneMet: false, allBlockedByGate: false, fingerprint: "f", continues: 0, stalledFingerprints: 0 };
  assert.equal(shouldContinue({ outcome: "aborted", run }).action, "ignore");
  assert.equal(shouldContinue({ outcome: "error", run }).action, "ignore");
  assert.equal(shouldContinue({ outcome: "completed", run: null }).action, "ignore");
  assert.equal(shouldContinue({ outcome: "completed", run: { ...run, doneMet: true } }).action, "ignore");
  return "4 ignore";
});

step("guard", "gate 全挡 / 次数上限 / 无进展：停止并写 handoff", () => {
  const base = { id: "x", active: true, doneMet: false, allBlockedByGate: false, fingerprint: "f", continues: 0, stalledFingerprints: 0 };
  const gate = shouldContinue({ outcome: "completed", run: { ...base, allBlockedByGate: true } });
  assert.equal(gate.action, "stop");
  assert.equal(gate.handoff, true);
  const capped = shouldContinue({ outcome: "completed", run: { ...base, continues: MAX_CONTINUES_PER_RUN } });
  assert.equal(capped.action, "stop");
  const stalled = shouldContinue({ outcome: "completed", run: { ...base, stalledFingerprints: MAX_CONTINUES_WITHOUT_PROGRESS } });
  assert.equal(stalled.action, "stop");
  assert.match(renderHandoff("x", "test"), /xr status/);
  return "3 stop";
});

step("guard", "正常推进：继续消息含 run 与第一步", () => {
  const decision = shouldContinue({
    outcome: "completed",
    run: { id: "run-1", active: true, doneMet: false, allBlockedByGate: false, fingerprint: "f", continues: 3, stalledFingerprints: 0 },
  });
  assert.equal(decision.action, "continue");
  assert.match(decision.message, /run-1/);
  assert.match(decision.message, /xr status/);
  return "continue";
});

step("guard", "指纹变化归零，不变则累加", () => {
  assert.equal(nextStall("a", "b", 2), 0);
  assert.equal(nextStall("a", "a", 2), 3);
  return "nextStall ok";
});

step("guard", "看门狗与压缩边界", () => {
  assert.equal(watchdogDue(0, 180_000, false), true);
  assert.equal(watchdogDue(0, 180_000, true), false);
  assert.equal(boundaryDecision({ contextTokens: 1_000, provider: "openai26" }), "continue");
  assert.equal(boundaryDecision({ contextTokens: 999_999, provider: "openai26" }), "compact");
  assert.equal(compactText("capsule", null), "capsule");
  return "watchdog/boundary ok";
});

// ---------- 3. 打包与安装预演（临时目录，不碰真实 HOME） ----------
const pkg = path.join(work, "pkg");
const fakeHome = path.join(work, "fake-home");
fs.mkdirSync(fakeHome, { recursive: true });

step("package", "dry-run 不落盘", () => {
  const out = execFileSync("bash", [path.join(root, "scripts/package-v4.sh"), "--dest", pkg, "--dry-run"], { encoding: "utf8" });
  assert.equal(fs.existsSync(pkg), false);
  assert.match(out, /交叉收录: 无/);
  return "no writes";
});

step("package", "导出后两个 manifest 互斥且入口存在", () => {
  execFileSync("bash", [path.join(root, "scripts/package-v4.sh"), "--dest", pkg], { encoding: "utf8" });
  const xrManifest = parseJson(fs.readFileSync(path.join(pkg, "x-rail/manifest.json"), "utf8"), "x-rail manifest");
  const pluginManifest = parseJson(fs.readFileSync(path.join(pkg, "model-recovery/manifest.json"), "utf8"), "model-recovery manifest");
  assert.ok(fs.existsSync(path.join(pkg, "x-rail", xrManifest.entry)));
  assert.ok(fs.existsSync(path.join(pkg, "model-recovery", pluginManifest.entry)));
  assert.equal(xrManifest.files.filter((file) => file.includes("failover")).length, 0);
  assert.equal(pluginManifest.files.filter((file) => file.includes("xr")).length, 0);
  return `${xrManifest.files.length}+${pluginManifest.files.length} files`;
});

step("package", "重复导出被拒绝", () => {
  const again = spawnSync("bash", [path.join(root, "scripts/package-v4.sh"), "--dest", pkg], { encoding: "utf8" });
  assert.notEqual(again.status, 0);
  assert.match(again.stderr, /拒绝导出/);
  return "rejected";
});

step("install", "临时 HOME 预演：dry-run 不创建文件", () => {
  const out = execFileSync("bash", [path.join(root, "skills/x-rail/install.sh"), "--home", fakeHome, "--dry-run"], { encoding: "utf8" });
  assert.equal(fs.existsSync(path.join(fakeHome, ".pi")), false);
  assert.match(out, /dry-run/);
  return "no writes";
});

step("install", "临时 HOME 安装：守卫入口存在，旧 failover 不加载", () => {
  execFileSync("bash", [path.join(root, "skills/x-rail/install.sh"), "--home", fakeHome], { encoding: "utf8" });
  const ext = path.join(fakeHome, ".pi/agent/extensions/x-rail");
  assert.ok(fs.existsSync(path.join(ext, "x-run-guard.ts")));
  assert.ok(fs.existsSync(path.join(ext, "host-events.ts")));
  assert.equal(fs.existsSync(path.join(ext, "x-failover.ts")), false);
  const manifest = fs.readFileSync(path.join(ext, "package.json"), "utf8");
  assert.match(manifest, /x-run-guard\.ts/);
  assert.doesNotMatch(manifest, /x-failover\.ts/);
  return "guard entry only";
});

// ---------- 汇总 ----------
const passed = results.filter((item) => item.passed).length;
const failed = results.length - passed;
const report = { workdir: work, passed, failed, results };
fs.writeFileSync(path.join(work, "report.json"), `${JSON.stringify(report, null, 2)}\n`);

for (const item of results) {
  console.log(`${item.passed ? "PASS" : "FAIL"} [${item.section}] ${item.name}${item.detail ? ` — ${item.detail}` : ""}`);
}
console.log(`\n${passed} passed, ${failed} failed（无模型调用；工作目录 ${work}）`);
if (failed) process.exitCode = 1;
