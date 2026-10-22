#!/usr/bin/env node
/**
 * 探针：失败轮里 ctx.model 是虚拟模型还是物理模型？网关标记到底有没有生效？
 *
 * 本地假模型先返回带网关文案的 finish_reason（Pi 会转成 assistant error），
 * 再返回成功。观察者记录 message_end 时的模型身份与最终 errorMessage。
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const pi = process.env.HOST_PROBE_PI || path.join(os.homedir(), ".hermes/node/bin/pi");
const plugin = path.join(root, "plugins/pi-model-recovery/index.ts");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-marker-"));
const observer = path.join(work, "observer.ts");
const home = path.join(work, "home");
const agentDir = path.join(home, ".pi/agent");
const project = path.join(work, "project");
for (const dir of [agentDir, project]) fs.mkdirSync(dir, { recursive: true });
// 观察者只用于本探针，写到临时目录，避免仓库里多一个无法纳入类型检查的文件。
fs.writeFileSync(observer, [
  'import fs from "node:fs";',
  'export default function observer(pi) {',
  '  pi.on("message_end", async (event, ctx) => {',
  '    const file = process.env.RECOVERY_OBSERVE_FILE;',
  '    if (!file) return;',
  '    const message = event.message;',
  '    if (message.role !== "assistant") return;',
  '    fs.appendFileSync(file, JSON.stringify({',
  '      provider: ctx.model?.provider ?? null,',
  '      model: ctx.model?.id ?? null,',
  '      stopReason: message.stopReason ?? null,',
  '      errorMessage: message.errorMessage ?? null,',
  '    }) + "\\n");',
  '  });',
  '}',
  '',
].join("\n"));

const observeFile = path.join(work, "observed.jsonl");
const requests = [];
let attempt = 0;
const server = http.createServer(async (request, response) => {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  let body = {};
  try { body = JSON.parse(raw); } catch { /* 空体按空处理 */ }
  requests.push({ url: request.url, model: body.model });
  attempt += 1;
  response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache" });
  const chunk = (delta, finish = null) => response.write(`data: ${JSON.stringify({ id: "marker-probe", object: "chat.completion.chunk", created: 1, model: body.model ?? "fixture-a", choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`);
  if (attempt === 1) {
    // 未知 finish_reason → Pi 生成 assistant error，文案里带网关标记文本。
    chunk({ role: "assistant", content: "partial" }, "The service is busy");
  } else {
    chunk({ role: "assistant", content: "RECOVERED" });
    chunk({}, "stop");
  }
  response.end("data: [DONE]\n\n");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

fs.writeFileSync(path.join(agentDir, "models.json"), JSON.stringify({
  providers: {
    "marker-probe": {
      baseUrl: `http://127.0.0.1:${port}/v1`,
      api: "openai-completions",
      apiKey: "local-fixture-key",
      models: ["fixture-a", "fixture-b"].map((id) => ({ id, name: id, reasoning: false, input: ["text"], contextWindow: 4096, maxTokens: 512, compat: { supportsDeveloperRole: false, supportsStore: false } })),
    },
  },
}, null, 2) + "\n");
fs.writeFileSync(path.join(agentDir, "auth.json"), "{}\n");
fs.writeFileSync(path.join(agentDir, "settings.json"), JSON.stringify({ defaultProvider: "marker-probe", defaultModel: "fixture-a", defaultThinkingLevel: "off", retry: { enabled: true, maxRetries: 2, baseDelayMs: 1, maxDelayMs: 1 } }, null, 2) + "\n");
fs.writeFileSync(path.join(work, "model-recovery.json"), JSON.stringify({
  schema: 1,
  chain: [{ provider: "marker-probe", model: "fixture-a" }, { provider: "marker-probe", model: "fixture-b" }],
  cooldownMs: 1000,
  gatewayCompatibility: true,
}, null, 2) + "\n");

const env = {
  PATH: `${path.dirname(process.execPath)}:${path.dirname(pi)}:/usr/bin:/bin`,
  HOME: home,
  TMPDIR: work,
  LANG: "en_US.UTF-8",
  PI_CODING_AGENT_DIR: agentDir,
  PI_CODING_AGENT_SESSION_DIR: path.join(work, "sessions"),
  PI_OFFLINE: "1",
  PI_TELEMETRY: "0",
  PI_MODEL_RECOVERY_CONFIG: path.join(work, "model-recovery.json"),
  RECOVERY_OBSERVE_FILE: observeFile,
};

const child = spawn(pi, [
  "--mode", "json", "--no-extensions", "--no-skills", "--no-prompt-templates",
  "--no-themes", "--no-context-files", "--no-mcp", "--thinking", "off",
  "--extension", plugin, "--extension", observer,
  "--provider", "model-recovery", "--model", "auto",
  "MARKER_PROBE: reply DONE.",
], { cwd: project, env, stdio: ["ignore", "pipe", "pipe"] });
const out = [];
const err = [];
child.stdout.on("data", (chunk) => out.push(chunk.toString("utf8")));
child.stderr.on("data", (chunk) => err.push(chunk.toString("utf8")));
const timer = setTimeout(() => child.kill("SIGTERM"), 60000);
const exit = await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", (code, signal) => resolve({ code, signal }));
});
clearTimeout(timer);
server.closeAllConnections();
await new Promise((resolve) => server.close(resolve));

const observed = fs.existsSync(observeFile)
  ? fs.readFileSync(observeFile, "utf8").split("\n").filter(Boolean).flatMap((line) => {
    try { return [JSON.parse(line)]; } catch { return []; }
  })
  : [];
const report = {
  work,
  exit,
  requests,
  observed,
  stderr: err.join("").slice(-800),
};
fs.writeFileSync(path.join(work, "report.json"), `${JSON.stringify(report, null, 2)}\n`);

const checks = [];
const check = (name, fn) => {
  try { fn(); checks.push({ name, passed: true }); } catch (error) { checks.push({ name, passed: false, error: error.message }); }
};

check("失败轮确实产生了 assistant error", () => {
  assert.ok(observed.length >= 1, `observed=${observed.length}`);
  assert.equal(observed[0].stopReason, "error", JSON.stringify(observed[0]));
});

check("失败轮的 ctx.model 记录（决定性事实）", () => {
  // 这条不判对错，只要求有值，便于报告里读出虚拟/物理。
  assert.ok(observed[0].provider, JSON.stringify(observed[0]));
});

check("网关标记在失败轮生效", () => {
  assert.match(String(observed[0].errorMessage ?? ""), /temporary gateway error/, JSON.stringify(observed[0]));
});

check("宿主 retry 换到链上下一个物理模型", () => {
  assert.equal(requests.length, 2, `requests=${requests.length}`);
  assert.deepEqual(requests.map((item) => item.model), ["fixture-a", "fixture-b"]);
});

const passed = checks.filter((item) => item.passed).length;
report.checks = checks;
report.passed = passed;
report.failed = checks.length - passed;
fs.writeFileSync(path.join(work, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
for (const item of checks) console.log(`${item.passed ? "PASS" : "FAIL"} ${item.name}${item.error ? ` — ${item.error}` : ""}`);
console.log(`\n${passed} passed, ${checks.length - passed} failed`);
console.log(JSON.stringify({ contextModelAtFailure: observed[0] ?? null, requests }, null, 2));
if (report.failed) process.exitCode = 1;
