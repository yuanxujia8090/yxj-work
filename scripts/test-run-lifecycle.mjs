import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pi = process.env.HOST_PROBE_PI || "/Users/yuanxj/.hermes/node/bin/pi";
const subagents = process.env.HOST_PROBE_SUBAGENTS || "/Users/yuanxj/.pi/agent/npm/node_modules/pi-subagents";
const piRoot = path.resolve(path.dirname(fs.realpathSync(pi)), "../..");
const versions = { pi: JSON.parse(fs.readFileSync(path.join(piRoot, "package.json"))).version, subagents: JSON.parse(fs.readFileSync(path.join(subagents, "package.json"))).version };
const fixtures = path.join(root, "scripts/fixtures/run-lifecycle");
const evidence = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-host-probe-"));
const agentDir = path.join(evidence, "agent");
const work = path.join(evidence, "workspace");
const home = path.join(evidence, "home");
for (const dir of [agentDir, work, home, path.join(agentDir, "agents"), path.join(agentDir, "extensions/subagent")]) fs.mkdirSync(dir, { recursive: true });
const write = (file, value) => fs.writeFileSync(path.join(evidence, file), typeof value === "string" ? value : `${JSON.stringify(value, null, 2)}\n`);
const jsonl = (file) => fs.existsSync(file) ? fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line)) : [];
const checks = [];
const check = (name, fn) => { try { fn(); checks.push({ name, passed: true }); } catch (error) { checks.push({ name, passed: false, error: error.message }); } };
const observer = path.join(fixtures, "observer.ts");
const calls = (mode) => ({ id: `probe_${mode}`, type: "function", function: { name: "probe_action", arguments: JSON.stringify({ mode }) } });
let scenario = "basic";
let parentLaunched = false;
let statusRequested = false;
const requests = [];
const server = http.createServer(async (request, response) => {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  const body = JSON.parse(raw);
  requests.push({ at: Date.now(), scenario, url: request.url, host: request.headers.host, body });
  write("requests.json", requests);
  const child = body.messages.some((message) => message.role === "system" && typeof message.content === "string" && message.content.includes('<active_agent name="probe-child"/>'));
  const hasResult = body.messages.some((message) => message.role === "tool");
  let toolCalls;
  if (scenario === "basic" && !hasResult) toolCalls = [calls("ok"), calls("fail"), calls("blocked")];
  if (scenario === "async" && child && !hasResult) toolCalls = [calls("child")];
  if (scenario === "async" && !child && !parentLaunched) {
    parentLaunched = true;
    toolCalls = [{ id: "probe_launch", type: "function", function: { name: "subagent", arguments: JSON.stringify({ agent: "probe-child", task: "HOST_PROBE_CHILD: call probe_action child once, then reply CHILD_DONE.", model: "host-probe/local", async: true, options: { timeoutMs: 30000 } }) } }];
  }
  if (scenario === "async" && !child && !statusRequested && JSON.stringify(body.messages).includes("Background task completed:")) {
    const receipt = body.messages.find((message) => message.role === "tool" && typeof message.content === "string" && message.content.includes("Async: probe-child"));
    const id = receipt?.content.match(/Async: probe-child \[([^\]]+)\]/)?.[1];
    if (id) {
      statusRequested = true;
      toolCalls = [{ id: "probe_status", type: "function", function: { name: "subagent", arguments: JSON.stringify({ action: "status", id }) } }];
    }
  }
  const text = child ? "CHILD_DONE" : "PARENT_DONE";
  response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache" });
  const chunk = (delta, finish_reason = null) => response.write(`data: ${JSON.stringify({ id: "host-probe", object: "chat.completion.chunk", created: 1, model: "local", choices: [{ index: 0, delta, finish_reason }] })}\n\n`);
  chunk({ role: "assistant", ...(toolCalls ? { tool_calls: toolCalls.map((call, index) => ({ index, ...call })) } : { content: text }) });
  chunk({}, toolCalls ? "tool_calls" : "stop");
  response.end("data: [DONE]\n\n");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
write("agent/auth.json", {});
write("agent/models.json", { providers: { "host-probe": { baseUrl: `http://127.0.0.1:${port}/v1`, api: "openai-completions", apiKey: "local-fixture-key", models: [{ id: "local", name: "Local lifecycle fixture", reasoning: false, input: ["text"], contextWindow: 32768, maxTokens: 1024, compat: { supportsDeveloperRole: false, supportsStore: false } }] } } });
write("agent/settings.json", { defaultProvider: "host-probe", defaultModel: "local", defaultThinkingLevel: "off", retry: { enabled: false }, subagents: { disableBuiltins: true, defaultModel: "host-probe/local", modelScope: { allow: ["host-probe/local"], enforce: true, strict: true } } });
write("agent/extensions/subagent/config.json", { toolActivation: "eager" });
write("agent/agents/probe-child.md", `---\nname: probe-child\ndescription: Local host lifecycle fixture\nmodel: host-probe/local\ntools: probe_action\nexcludeTools: contact_supervisor, subagent, subagent_supervisor, bg_wait\nextensions: ${observer}\nallowedAgents:\ninheritProjectContext: false\ninheritGlobalContext: false\ninheritSkills: false\nacceptanceRole: read-only\nacceptance: {"level":"none","reason":"local lifecycle fixture"}\nsystemPromptMode: replace\n---\nLocal fixture. Call probe_action with mode child once, then return CHILD_DONE. Never delegate.\n`);
// Deliberate env allowlist: no personal providers, credentials, proxies, NODE_OPTIONS, or package config.
const env = { PATH: `${path.dirname(process.execPath)}:${path.dirname(pi)}:/usr/bin:/bin`, HOME: home, TMPDIR: evidence, LANG: "en_US.UTF-8", PI_CODING_AGENT_DIR: agentDir, PI_CODING_AGENT_SESSION_DIR: path.join(evidence, "sessions"), PI_OFFLINE: "1", PI_TELEMETRY: "0", PI_SUBAGENT_PI_BINARY: pi, HOST_PROBE_EVENTS: path.join(evidence, "events.jsonl"), HOST_PROBE_NETWORK_LOG: path.join(evidence, "network.jsonl"), HOST_PROBE_PORT: String(port), NODE_OPTIONS: `--require=${path.join(fixtures, "network-guard.cjs")}` };
write("environment.json", env);
const common = ["--mode", "json", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-mcp", "--provider", "host-probe", "--model", "local", "--thinking", "off", "--extension", observer];
async function run(name, extra, prompt) {
  const args = [...common, ...extra, prompt];
  write(`${name}.command.json`, { command: pi, args, cwd: work });
  const child = spawn(pi, args, { cwd: work, env, stdio: ["ignore", "pipe", "pipe"] });
  const stdout = fs.createWriteStream(path.join(evidence, `${name}.stdout.jsonl`));
  const stderr = fs.createWriteStream(path.join(evidence, `${name}.stderr.txt`));
  child.stdout.pipe(stdout); child.stderr.pipe(stderr);
  const timer = setTimeout(() => child.kill("SIGTERM"), 45000);
  const result = await new Promise((resolve, reject) => { child.on("error", reject); child.on("close", (code, signal) => resolve({ code, signal })); });
  clearTimeout(timer);
  await Promise.all([new Promise((resolve) => stdout.end(resolve)), new Promise((resolve) => stderr.end(resolve))]);
  write(`${name}.exit.json`, result);
  return jsonl(path.join(evidence, `${name}.stdout.jsonl`));
}
function events() { return jsonl(env.HOST_PROBE_EVENTS); }
function sessionFor(pid) { return events().find((event) => event.type === "session_start" && event.pid === pid); }
function files(dir, name) {
  return fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? files(path.join(dir, entry.name), name) : entry.name === name ? [path.join(dir, entry.name)] : []) : [];
}
let fatal;
try {
  const basic = await run("basic", ["--tools", "probe_action"], "HOST_PROBE_BASIC");
  const start = events().find((event) => event.type === "session_start");
  check("extension loaded in real Pi", () => { assert.ok(start); assert.ok(events().some((event) => event.type === "extension_loaded" && event.pid === start.pid)); });
  const basicEvents = events().filter((event) => event.pid === start?.pid);
  for (const mode of ["ok", "fail", "blocked"]) {
    const id = `probe_${mode}`;
    const types = basicEvents.filter((event) => event.toolCallId === id).map((event) => event.type);
    write(`order-${mode}.json`, types);
    check(`${mode}: observed ordering and pairing`, () => {
      assert.deepEqual(types, mode === "blocked" ? ["tool_execution_start", "tool_call", "block_decision", "tool_execution_end"] : ["tool_execution_start", "tool_call", "execute_enter", "tool_result", "tool_execution_end"]);
      const end = basicEvents.find((event) => event.toolCallId === id && event.type === "tool_execution_end");
      assert.equal(end.isError, mode !== "ok");
      if (mode !== "blocked") assert.equal(basicEvents.find((event) => event.toolCallId === id && event.type === "tool_result").isError, mode === "fail");
      const transcriptResults = basic.flatMap((event) => event.type === "message_end" && event.message?.role === "toolResult" && event.message.toolCallId === id ? [event.message] : []);
      assert.equal(transcriptResults.length, 1);
      assert.equal(transcriptResults[0].isError, mode !== "ok");
    });
  }
  check("blocked tool never enters execute or tool_result hook", () => {
    assert.equal(basicEvents.filter((event) => event.toolCallId === "probe_blocked" && ["execute_enter", "tool_result"].includes(event.type)).length, 0);
  });
  check("basic turn and settle ordering", () => {
    const types = basicEvents.map((event) => event.type);
    assert.ok(types.includes("block_decision"));
    assert.ok(types.indexOf("turn_end") > types.indexOf("block_decision"));
    assert.ok(types.indexOf("agent_end") > types.indexOf("turn_end"));
    assert.ok(types.indexOf("agent_before_settle") > types.indexOf("agent_end"));
    assert.ok(types.indexOf("agent_settled") > types.indexOf("agent_before_settle"));
  });
  if (!start?.sessionFile) throw new Error("basic Pi did not expose persisted session file");
  scenario = "resume";
  await run("resume", ["--tools", "probe_action", "--session", start.sessionFile], "HOST_PROBE_RESUME");
  await run("new", ["--tools", "probe_action"], "HOST_PROBE_NEW");
  const starts = events().filter((event) => event.type === "session_start");
  check("--session restart keeps identity; new session changes identity", () => {
    assert.equal(starts.length, 3);
    assert.notEqual(starts[0].pid, starts[1].pid);
    assert.equal(starts[0].sessionId, starts[1].sessionId);
    assert.equal(starts[0].sessionFile, starts[1].sessionFile);
    assert.notEqual(starts[0].sessionId, starts[2].sessionId);
  });
  scenario = "async";
  const asyncEvents = await run("async", ["--tools", "subagent", "--extension", path.join(subagents, "index.js")], "HOST_PROBE_ASYNC: authorized local fixture subagent");
  const launch = events().find((event) => event.type === "tool_result" && event.toolCallId === "probe_launch");
  write("async-launch.json", launch || { error: "No subagent tool_result" });
  check("subagent launch receipt", () => { assert.ok(launch, "No subagent tool_result"); assert.equal(launch.isError, false, JSON.stringify(launch)); });
  const statuses = files(evidence, "status.json").map((file) => ({ file, status: JSON.parse(fs.readFileSync(file, "utf8")) }));
  write("async-statuses.json", statuses);
  const childExecution = events().find((event) => event.type === "execute_enter" && event.mode === "child");
  check("async child actually executed with isolated identity and minimal tools", () => {
    assert.ok(childExecution, "No child execute_enter; inspect async status/runner stderr");
    assert.notEqual(childExecution.pid, launch.pid);
    assert.notEqual(childExecution.sessionId, launch.sessionId);
    assert.deepEqual(childExecution.activeTools, ["probe_action"]);
    assert.equal(events().filter((event) => event.pid === launch.pid && event.toolCallId === "probe_child").length, 0);
    assert.equal(events().find((event) => event.type === "tool_call" && event.toolCallId === "probe_child").parentToolCallId, undefined);
    assert.ok(sessionFor(childExecution.pid));
  });
  check("async terminal state persisted and delivered to parent", () => {
    const terminal = statuses.find(({ status }) => status.runId === launch?.details?.runId);
    assert.ok(terminal, "No status matching launch runId");
    assert.equal(terminal.status.state, "complete");
    assert.equal(terminal.status.toolCallId, "probe_launch");
    assert.equal(terminal.status.steps[0].status, "complete");
    assert.equal(terminal.status.steps[0].exitCode, 0);
    assert.equal(terminal.status.steps[0].sessionFile, childExecution.sessionFile);
    assert.ok(fs.readFileSync(terminal.status.outputFile, "utf8").includes("CHILD_DONE"));
    assert.equal(terminal.status.processTerminal.state, "observed");
    assert.equal(terminal.status.processTerminal.instances[0].exitCode, 0);
    assert.equal(terminal.status.steps[0].capabilityAudit.effectiveTools.includes("subagent"), false);
    const lifecycle = jsonl(path.join(path.dirname(terminal.file), "events.jsonl"));
    assert.ok(lifecycle.some((event) => event.type === "subagent.run.completed" && event.runId === launch.details.runId));
    assert.ok(lifecycle.some((event) => event.type === "subagent.run.process_terminal" && event.runId === launch.details.runId));
    assert.ok(lifecycle.some((event) => event.type === "tool_execution_end" && event.toolCallId === "probe_child" && event.subagentRunId === launch.details.runId));
    write("async-lifecycle-summary.json", lifecycle.filter((event) => ["subagent.run.completed", "subagent.run.process_terminal", "tool_execution_end"].includes(event.type)));
    const statusResult = events().find((event) => event.type === "tool_result" && event.toolCallId === "probe_status");
    assert.ok(statusResult, "No one-shot status result after completion notification");
    assert.equal(statusResult.isError, false);
    assert.equal(statusResult.details.runId, launch.details.runId);
    assert.equal(statusResult.details.lifecycleStatus.processTerminal.state, "observed");
    assert.ok(asyncEvents.some((event) => event.type === "message_end" && event.message?.customType === "subagent-notify" && JSON.stringify(event.message).includes("CHILD_DONE") && JSON.stringify(event.message).includes(launch.details.runId)), "No correlated completion message in parent JSON stream");
  });
  check("parent launch result precedes child completion", () => {
    const childSettled = events().find((event) => event.type === "agent_settled" && event.pid === childExecution?.pid);
    assert.ok(childSettled);
    assert.ok(launch.at < childSettled.at);
  });
  check("all four parent invocations exit successfully", () => {
    for (const name of ["basic", "resume", "new", "async"]) assert.deepEqual(JSON.parse(fs.readFileSync(path.join(evidence, `${name}.exit.json`))), { code: 0, signal: null });
  });
  check("all Pi processes inherit isolation and connect only to fixture", () => {
    const network = jsonl(env.HOST_PROBE_NETWORK_LOG);
    for (const event of network.filter((item) => item.type === "process")) { assert.equal(event.agentDir, agentDir); assert.equal(event.home, home); assert.equal(event.offline, "1"); }
    assert.equal(network.filter((item) => item.type === "process").length, 5);
    assert.ok(network.some((item) => item.pid === childExecution?.pid && item.type === "connect"));
    assert.equal(network.filter((item) => item.allowed === false).length, 0);
    assert.ok(requests.every((item) => item.host === `127.0.0.1:${port}` && item.url === "/v1/chat/completions" && item.body.model === "local"));
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(agentDir, "auth.json"), "utf8")), {});
  });
} catch (error) { fatal = error.stack; } finally {
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
  const passed = checks.filter((item) => item.passed).length;
  const report = { evidence, pi, subagents, versions, checks, passed, failed: checks.length - passed, requests: requests.length, fatal };
  write("report.json", report);
  console.log(JSON.stringify(report, null, 2));
  if (fatal || report.failed) process.exitCode = 1;
}
