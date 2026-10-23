#!/usr/bin/env node
/**
 * 已安装布局验证：把技能与守卫装进临时 HOME，再用真实 Pi + 本地假模型跑一轮任务。
 *
 * 目的：验证“装好之后守卫能不能找到 xr”这个此前致命的问题。
 * 不联网、不碰真实 HOME、不装模型插件。
 */
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";

const root = path.resolve(import.meta.dirname, "..");
const pi = process.env.HOST_PROBE_PI || path.join(os.homedir(), ".hermes/node/bin/pi");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-install-"));
const home = path.join(work, "home");
const project = path.join(work, "project");
fs.mkdirSync(home, { recursive: true });
fs.mkdirSync(project, { recursive: true });

function parseJson(text, label) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${label} 不是合法 JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

const checks = [];
const check = (name, fn) => {
  try { fn(); checks.push({ name, passed: true }); }
  catch (error) { checks.push({ name, passed: false, error: error.message }); }
};

// 1) 安装到临时 HOME
const pkg = path.join(work, "package");
const exported = spawnSync("bash", [path.join(root, "scripts/package-v4.sh"), "--dest", pkg], { encoding: "utf8" });
check("导出正式 x-rail 包", () => assert.equal(exported.status, 0, exported.stdout + exported.stderr));
const agentDir = path.join(home, ".pi/agent");
const piInstall = spawnSync(pi, ["install", path.join(pkg, "x-rail")], {
  encoding: "utf8",
  env: { ...process.env, HOME: home, PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: "1", PI_TELEMETRY: "0" },
});
check("Pi 安装正式包到临时 HOME", () => assert.equal(piInstall.status, 0, piInstall.stdout + piInstall.stderr));

const packageDir = path.join(pkg, "x-rail");
const extDir = path.join(packageDir, "extensions");
const installedXr = path.join(packageDir, "skills/x-rail/scripts/xr");

check("安装清单只加载任务守卫入口", () => {
  const manifest = parseJson(fs.readFileSync(path.join(packageDir, "package.json"), "utf8"), "package.json");
  const entries = manifest.pi.extensions;
  assert.deepEqual(entries, ["./extensions/x-run-guard.ts"], JSON.stringify(entries));
  assert.ok(fs.existsSync(path.join(extDir, "x-run-guard.ts")));
  assert.ok(fs.existsSync(path.join(packageDir, "lib/x-rail/host-events.ts")));
  assert.deepEqual(fs.readdirSync(extDir).filter((name) => name.endsWith(".ts")), ["x-run-guard.ts"]);
});

check("已安装路径下能找到 xr", () => {
  assert.ok(fs.existsSync(installedXr), `missing ${installedXr}`);
  const out = spawnSync("python3", [installedXr, "--help"], { encoding: "utf8" });
  assert.equal(out.status, 0, out.stdout + out.stderr);
});

// 2) 本地假模型 + 任务
const requests = [];
const server = http.createServer(async (request, response) => {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  let body = {};
  try { body = JSON.parse(raw); } catch { /* 记录不到就按空处理 */ }
  requests.push({ at: Date.now(), url: request.url, model: body.model });
  response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache" });
  const chunk = (delta, finish = null) => response.write(`data: ${JSON.stringify({ id: "install-probe", object: "chat.completion.chunk", created: 1, model: "fixture-a", choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`);
  chunk({ role: "assistant", content: "INSTALL_DONE" });
  chunk({}, "stop");
  response.end("data: [DONE]\n\n");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

fs.writeFileSync(path.join(agentDir, "models.json"), JSON.stringify({
  providers: {
    "install-probe": {
      baseUrl: `http://127.0.0.1:${port}/v1`,
      api: "openai-completions",
      apiKey: "local-fixture-key",
      models: [{ id: "fixture-a", name: "fixture-a", reasoning: false, input: ["text"], contextWindow: 4096, maxTokens: 512, compat: { supportsDeveloperRole: false, supportsStore: false } }],
    },
  },
}, null, 2) + "\n");
fs.writeFileSync(path.join(agentDir, "auth.json"), "{}\n");
const settingsPath = path.join(agentDir, "settings.json");
const settings = parseJson(fs.readFileSync(settingsPath, "utf8"), "settings.json");
Object.assign(settings, { defaultProvider: "install-probe", defaultModel: "fixture-a", defaultThinkingLevel: "off", retry: { enabled: true, maxRetries: 1, baseDelayMs: 1 } });
fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n");

const session = randomUUID();
fs.writeFileSync(path.join(project, "note.md"), "pending\n");
const xr = (args) => spawnSync("python3", [installedXr, ...args], { cwd: project, encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PI_SESSION_ID: "" } });

check("用已安装 xr 初始化任务", () => {
  const init = xr(["init", "installed", "--session", session]);
  assert.equal(init.status, 0, init.stdout + init.stderr);
  const planned = xr(["--session", session, "plan", "add", "u1", "待做单元", "--deps", "none", "--files", "note.md", "--verify", "test -f note.md"]);
  assert.equal(planned.status, 0, planned.stdout + planned.stderr);
});

const runDir = path.join(project, ".work-docs/runs", fs.readFileSync(path.join(project, ".work-docs/runs/ACTIVE"), "utf8").trim());
const env = {
  PATH: `${path.dirname(process.execPath)}:${path.dirname(pi)}:/usr/bin:/bin`,
  HOME: home,
  TMPDIR: work,
  LANG: "en_US.UTF-8",
  PI_CODING_AGENT_DIR: agentDir,
  PI_CODING_AGENT_SESSION_DIR: path.join(work, "sessions"),
  PI_OFFLINE: "1",
  PI_TELEMETRY: "0",
  // 关键：不设 X_RAIL_XR，让守卫只能靠安装布局找 xr。
};
const args = [
  "--mode", "json", "--no-skills", "--no-prompt-templates",
  "--no-themes", "--no-context-files", "--no-mcp", "--thinking", "off",
  "--provider", "install-probe", "--model", "fixture-a",
  "--session-id", session,
  "INSTALL_PROBE: reply DONE.",
];
const child = spawn(pi, args, { cwd: project, env, stdio: ["ignore", "pipe", "pipe"] });
const stdout = [];
const stderr = [];
child.stdout.on("data", (chunk) => stdout.push(chunk.toString("utf8")));
child.stderr.on("data", (chunk) => stderr.push(chunk.toString("utf8")));
const timer = setTimeout(() => child.kill("SIGTERM"), 90000);
const exit = await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", (code, signal) => resolve({ code, signal }));
});
clearTimeout(timer);
fs.writeFileSync(path.join(work, "pi.stdout.jsonl"), stdout.join(""));
fs.writeFileSync(path.join(work, "pi.stderr.txt"), stderr.join(""));

const eventsPath = path.join(runDir, "events.jsonl");
const events = fs.existsSync(eventsPath)
  ? fs.readFileSync(eventsPath, "utf8").split("\n").filter(Boolean).map((line) => parseJson(line, "events.jsonl line"))
  : [];

check("真实 Pi 跑通且守卫绑定成功", () => {
  assert.equal(exit.code, 0, stderr.join("").slice(0, 800));
  assert.ok(events.some((event) => event.type === "bind"), `events: ${events.map((event) => event.type).join(",")}`);
});

check("守卫能通过安装布局调用 xr 并续跑", () => {
  const resumes = events.filter((event) => event.type === "resume");
  assert.ok(resumes.length >= 1, `resume=${resumes.length}；说明 xr 没被找到`);
  const guardState = path.join(runDir, "guard.json");
  assert.ok(fs.existsSync(guardState), "guard.json 缺失，说明 xr guard set 没跑通");
  const memory = parseJson(fs.readFileSync(guardState, "utf8"), "guard.json");
  assert.ok(memory.continues >= 1, JSON.stringify(memory));
});

check("无进展时停下并写 handoff", () => {
  const handoff = path.join(runDir, "handoff.md");
  assert.ok(fs.existsSync(handoff), "handoff.md 缺失，说明守卫没停");
  assert.match(fs.readFileSync(handoff, "utf8"), /连续 3 次续跑|xr status/);
});

check("全程只连本地假模型", () => {
  assert.ok(requests.length >= 1);
  assert.ok(requests.every((item) => item.url === "/v1/chat/completions"));
});

server.closeAllConnections();
await new Promise((resolve) => server.close(resolve));
const passed = checks.filter((item) => item.passed).length;
const report = { work, home, project, runDir, passed, failed: checks.length - passed, checks, requests: requests.length };
fs.writeFileSync(path.join(work, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
for (const item of checks) console.log(`${item.passed ? "PASS" : "FAIL"} ${item.name}${item.error ? ` — ${item.error}` : ""}`);
console.log(`\n${passed} passed, ${checks.length - passed} failed（临时 HOME：${home}）`);
if (report.failed) process.exitCode = 1;
