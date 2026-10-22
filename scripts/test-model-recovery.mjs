/**
 * 模型恢复插件的宿主探针。
 *
 * 默认只用本地假模型：不联网、不读个人凭据。
 * 真实模型分支需显式 RECOVERY_REAL_MODEL=1，且只在用户已授权时运行。
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";

const root = path.resolve(import.meta.dirname, "..");
const plugin = path.join(root, "plugins/pi-model-recovery/index.ts");
const pi = process.env.HOST_PROBE_PI || path.join(os.homedir(), ".hermes/node/bin/pi");
const evidence = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-recovery-"));
const agentDir = path.join(evidence, "agent");
const work = path.join(evidence, "workspace");
const home = path.join(evidence, "home");
for (const dir of [agentDir, work, home, path.join(agentDir, "extensions")]) fs.mkdirSync(dir, { recursive: true });

const write = (rel, value) => {
  const file = path.join(evidence, rel);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, typeof value === "string" ? value : `${JSON.stringify(value, null, 2)}\n`);
};
const checks = [];
const check = (name, fn) => {
  try { fn(); checks.push({ name, passed: true }); }
  catch (error) { checks.push({ name, passed: false, error: error.message }); }
};

const requests = [];
/** 下一个请求返回 503，用于验证宿主 retry 时插件换链。 */
let failNext = false;
const server = http.createServer(async (request, response) => {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  let body = {};
  try { body = JSON.parse(raw); } catch { /* 记录原文即可 */ }
  requests.push({ at: Date.now(), url: request.url, host: request.headers.host, body });
  write("requests.json", requests);
  if (failNext) {
    failNext = false;
    response.writeHead(503, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: { message: "The service is busy" } }));
    return;
  }
  response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache" });
  const chunk = (delta, finish = null) => response.write(`data: ${JSON.stringify({ id: "recovery-probe", object: "chat.completion.chunk", created: 1, model: body.model ?? "fixture-a", choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`);
  chunk({ role: "assistant", content: "RECOVERY_DONE" });
  chunk({}, "stop");
  response.end("data: [DONE]\n\n");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

write("agent/models.json", {
  providers: {
    "host-probe": {
      baseUrl: `http://127.0.0.1:${port}/v1`,
      api: "openai-completions",
      apiKey: "local-fixture-key",
      models: ["fixture-a", "fixture-b"].map((id) => ({
        id, name: id, reasoning: false, input: ["text"], contextWindow: 32768, maxTokens: 1024,
        compat: { supportsDeveloperRole: false, supportsStore: false },
      })),
    },
  },
});
write("agent/auth.json", {});
write("agent/settings.json", { defaultProvider: "host-probe", defaultModel: "fixture-a", defaultThinkingLevel: "off", retry: { enabled: true, maxRetries: 2, baseDelayMs: 1, maxDelayMs: 1 } });

const env = {
  PATH: `${path.dirname(process.execPath)}:${path.dirname(pi)}:/usr/bin:/bin`,
  HOME: home,
  TMPDIR: evidence,
  LANG: "en_US.UTF-8",
  PI_CODING_AGENT_DIR: agentDir,
  PI_CODING_AGENT_SESSION_DIR: path.join(evidence, "sessions"),
  PI_OFFLINE: "1",
  PI_TELEMETRY: "0",
  PI_MODEL_RECOVERY_CONFIG: path.join(evidence, "model-recovery.json"),
};

const base = [
  "--mode", "json", "--no-extensions", "--no-skills", "--no-prompt-templates",
  "--no-themes", "--no-context-files", "--no-mcp", "--thinking", "off",
];

async function run(name, extra, prompt, timeoutMs = 45000) {
  const before = requests.length;
  const child = spawn(pi, [...base, ...extra, prompt], { cwd: work, env, stdio: ["ignore", "pipe", "pipe"] });
  const out = [];
  const err = [];
  child.stdout.on("data", (chunk) => out.push(chunk.toString("utf8")));
  child.stderr.on("data", (chunk) => err.push(chunk.toString("utf8")));
  const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
  const result = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (code, signal) => resolve({ code, signal }));
  });
  clearTimeout(timer);
  const stdout = out.join("");
  const stderr = err.join("");
  write(`${name}.stdout.jsonl`, stdout);
  write(`${name}.stderr.txt`, stderr);
  write(`${name}.exit.json`, result);
  return { ...result, stdout, stderr, requests: requests.length - before };
}

const messages = (stdout) => stdout.split("\n").filter(Boolean).flatMap((line) => {
  try { return [JSON.parse(line)]; } catch { return []; }
});

// A. 没有配置文件：插件可加载，但不注册虚拟模型，零请求。
fs.rmSync(path.join(evidence, "model-recovery.json"), { force: true });
const noConfig = await run("no-config", ["--extension", plugin, "--provider", "model-recovery", "--model", "auto"], "RECOVERY: ping");
check("未配置：不注册虚拟模型且不发请求", () => {
  assert.equal(noConfig.requests, 0);
  assert.notEqual(noConfig.code, 0);
  assert.match(`${noConfig.stdout}${noConfig.stderr}`, /model-recovery\/auto|not found|unknown/i);
});

// B. 配置结构无效：同样不注册、不请求。
write("model-recovery.json", { schema: 2, chain: [{ provider: "host-probe", model: "fixture-a" }] });
const badConfig = await run("bad-config", ["--extension", plugin, "--provider", "model-recovery", "--model", "auto"], "RECOVERY: ping");
check("配置无效：不注册虚拟模型且不发请求", () => {
  assert.equal(badConfig.requests, 0);
  assert.notEqual(badConfig.code, 0);
});

// C. 合法配置但链中模型不存在：注册成功，route 报精确原因，零请求。
write("model-recovery.json", { schema: 1, chain: [{ provider: "host-probe", model: "missing-x" }], cooldownMs: 1000 });
const missing = await run("missing-model", ["--extension", plugin, "--provider", "model-recovery", "--model", "auto"], "RECOVERY: ping");
check("链中模型不可用：零请求且原因精确", () => {
  assert.equal(missing.requests, 0, "不能退回到其他物理模型");
  assert.match(`${missing.stdout}${missing.stderr}`, /配置的模型不可用或无凭据：host-probe\/missing-x/);
});

// D. 正常路由：虚拟模型请求打到配置里的物理模型。
write("model-recovery.json", { schema: 1, chain: [{ provider: "host-probe", model: "fixture-a" }], cooldownMs: 1000 });
const routed = await run("routed", ["--extension", plugin, "--provider", "model-recovery", "--model", "auto"], "RECOVERY: ping");
check("路由到配置的物理模型且只发一次请求", () => {
  assert.equal(routed.code, 0, routed.stderr);
  assert.equal(routed.requests, 1);
  assert.equal(requests[0].body.model, "fixture-a");
});

// E. 暂时性失败：宿主 retry 时插件选链上下一个模型。
write("model-recovery.json", {
  schema: 1,
  chain: [{ provider: "host-probe", model: "fixture-a" }, { provider: "host-probe", model: "fixture-b" }],
  cooldownMs: 1000,
});
failNext = true;
const retried = await run("retry", ["--extension", plugin, "--provider", "model-recovery", "--model", "auto"], "RECOVERY: ping");
check("暂时性失败后 retry 换到链上下一个物理模型", () => {
  assert.equal(retried.code, 0, retried.stderr);
  assert.equal(retried.requests, 2, `requests=${retried.requests}`);
  const models = requests.slice(-2).map((item) => item.body.model);
  assert.deepEqual(models, ["fixture-a", "fixture-b"]);
});

// F. 真实模型分支：默认不跑，需显式授权。
if (process.env.RECOVERY_REAL_MODEL === "1") {
  const realAgentDir = process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".pi", "agent");
  write("model-recovery-real.json", { schema: 1, chain: [{ provider: "bai", model: "deepseek-v4.1-flash" }], cooldownMs: 600000 });
  const realEnv = {
    ...process.env,
    PI_CODING_AGENT_DIR: realAgentDir,
    PI_MODEL_RECOVERY_CONFIG: path.join(evidence, "model-recovery-real.json"),
  };
  const child = spawn(pi, [...base, "--extension", plugin, "--provider", "model-recovery", "--model", "model-recovery/auto", "RECOVERY: 只回复 OK 两个字符"], {
    cwd: work, env: realEnv, stdio: ["ignore", "pipe", "pipe"],
  });
  const out = [];
  child.stdout.on("data", (chunk) => out.push(chunk.toString("utf8")));
  const timer = setTimeout(() => child.kill("SIGTERM"), 120000);
  const result = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (code) => resolve({ code }));
  });
  clearTimeout(timer);
  const stdout = out.join("");
  write("real-model.stdout.jsonl", stdout);
  check("真实模型：虚拟模型路由到 bai/deepseek-v4.1-flash", () => {
    assert.equal(result.code, 0);
    const assistant = messages(stdout).filter((item) => item.type === "message_end" && item.message?.role === "assistant");
    assert.ok(assistant.length >= 1, "no assistant message");
    assert.equal(assistant.at(-1).message.model, "deepseek-v4.1-flash");
    assert.equal(assistant.at(-1).message.content?.some?.((part) => part.type === "text" && /OK/.test(part.text ?? "")), true, JSON.stringify(assistant.at(-1)).slice(0, 400));
  });
} else {
  checks.push({ name: "真实模型分支", passed: true, skipped: "RECOVERY_REAL_MODEL!=1" });
}

server.closeAllConnections();
await new Promise((resolve) => server.close(resolve));
const passed = checks.filter((item) => item.passed).length;
const report = { evidence, pi, port, checks, passed, failed: checks.length - passed, requests: requests.length };
write("report.json", report);
console.log(JSON.stringify(report, null, 2));
if (report.failed) process.exitCode = 1;
