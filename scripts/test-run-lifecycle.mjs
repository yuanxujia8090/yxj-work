import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pi = process.env.HOST_PROBE_PI || "/Users/yuanxj/.hermes/node/bin/pi";
const subagents = process.env.HOST_PROBE_SUBAGENTS || "/Users/yuanxj/.pi/agent/npm/node_modules/pi-subagents";
const piRoot = path.resolve(path.dirname(fs.realpathSync(pi)), "../..");
const parse = (text) => {
  try { return JSON.parse(text); }
  catch (error) { throw new Error(`host-probe invalid JSON: ${error.message}`, { cause: error }); }
};
const versions = { pi: parse(fs.readFileSync(path.join(piRoot, "package.json"))).version, subagents: parse(fs.readFileSync(path.join(subagents, "package.json"))).version };
const fixtures = path.join(root, "scripts/fixtures/run-lifecycle");
const evidence = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-host-probe-"));
const agentDir = path.join(evidence, "agent");
const work = path.join(evidence, "workspace");
const home = path.join(evidence, "home");
for (const dir of [agentDir, work, home, path.join(agentDir, "agents"), path.join(agentDir, "extensions/subagent")]) fs.mkdirSync(dir, { recursive: true });
const write = (file, value) => fs.writeFileSync(path.join(evidence, file), typeof value === "string" ? value : `${JSON.stringify(value, null, 2)}\n`);
const jsonl = (file) => fs.existsSync(file) ? fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((line) => parse(line)) : [];
const checks = [];
const check = (name, fn) => { try { fn(); checks.push({ name, passed: true }); } catch (error) { checks.push({ name, passed: false, error: error.message }); } };
const observer = path.join(fixtures, "observer.ts");
const calls = (mode) => ({ id: `probe_${mode}`, type: "function", function: { name: "probe_action", arguments: JSON.stringify({ mode }) } });
const readCall = { id: "probe_read", type: "function", function: { name: "read", arguments: JSON.stringify({ path: "README.md" }) } };
let scenario = "basic";
let parentLaunched = false;
let statusRequested = false;
let retryAttempted = false;
const requests = [];
const server = http.createServer(async (request, response) => {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  let body;
  try { body = JSON.parse(raw); } catch { response.writeHead(400).end(); return; }
  requests.push({ at: Date.now(), scenario, url: request.url, host: request.headers.host, body });
  write("requests.json", requests);
  const child = body.messages.some((message) => message.role === "system" && typeof message.content === "string" && message.content.includes('<active_agent name="probe-child"/>'));
  const hasResult = body.messages.some((message) => message.role === "tool");
  let toolCalls;
  if (scenario === "basic" && !hasResult) toolCalls = [calls("ok"), calls("fail"), calls("blocked")];
  if (scenario === "guard" && !hasResult) toolCalls = [readCall, calls("ok"), calls("fail"), calls("blocked")];
  if (scenario === "retry" && !retryAttempted) {
    retryAttempted = true;
    response.writeHead(503, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: { message: "gateway_concurrency_limit" } }));
    return;
  }
  if (scenario === "async" && child && !hasResult) toolCalls = [calls("child")];
  if (scenario === "async" && !child && !parentLaunched) {
    parentLaunched = true;
    toolCalls = [{ id: "probe_launch", type: "function", function: { name: "subagent", arguments: JSON.stringify({ agent: "probe-child", task: "HOST_PROBE_CHILD: call probe_action child once, then reply CHILD_DONE.", model: "host-probe/fixture-a", async: true, options: { timeoutMs: 30000 } }) } }];
  }
  if (scenario === "async" && !child && !statusRequested && JSON.stringify(body.messages).includes("Background task completed:")) {
    const receipt = body.messages.find((message) => message.role === "tool" && typeof message.content === "string" && message.content.includes("Async: probe-child"));
    const id = receipt?.content.match(/Async: probe-child \[([^\]]+)\]/)?.[1];
    if (id) {
      statusRequested = true;
      toolCalls = [{ id: "probe_status", type: "function", function: { name: "subagent", arguments: JSON.stringify({ action: "status", id }) } }];
    }
  }
  if (scenario === "rpc" && !hasResult) {
    // 慢回复：留出窗口让客户端发真实 abort。
    await new Promise((resolve) => setTimeout(resolve, 1500));
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
write("agent/models.json", { providers: { "host-probe": { baseUrl: `http://127.0.0.1:${port}/v1`, api: "openai-completions", apiKey: "local-fixture-key", models: ["fixture-a", "fixture-b"].map((id) => ({ id, name: id, reasoning: false, input: ["text"], contextWindow: 32768, maxTokens: 1024, compat: { supportsDeveloperRole: false, supportsStore: false } })) } } });
write("agent/settings.json", { defaultProvider: "host-probe", defaultModel: "fixture-a", defaultThinkingLevel: "off", retry: { enabled: true, maxRetries: 1, baseDelayMs: 1, maxDelayMs: 1 }, subagents: { disableBuiltins: true, defaultModel: "host-probe/fixture-a", modelScope: { allow: ["host-probe/fixture-a", "host-probe/fixture-b", "host-probe/auto"], enforce: true, strict: true } } });
write("agent/extensions/subagent/config.json", { toolActivation: "eager" });
write("agent/agents/probe-child.md", `---\nname: probe-child\ndescription: Local host lifecycle fixture\nmodel: host-probe/fixture-a\ntools: probe_action\nexcludeTools: contact_supervisor, subagent, subagent_supervisor, bg_wait\nextensions: ${observer}\nallowedAgents:\ninheritProjectContext: false\ninheritGlobalContext: false\ninheritSkills: false\nacceptanceRole: read-only\nacceptance: {"level":"none","reason":"local lifecycle fixture"}\nsystemPromptMode: replace\n---\nLocal fixture. Call probe_action with mode child once, then return CHILD_DONE. Never delegate.\n`);
// Deliberate env allowlist: no personal providers, credentials, proxies, NODE_OPTIONS, or package config.
const env = { PATH: `${path.dirname(process.execPath)}:${path.dirname(pi)}:/usr/bin:/bin`, HOME: home, TMPDIR: evidence, LANG: "en_US.UTF-8", PI_CODING_AGENT_DIR: agentDir, PI_CODING_AGENT_SESSION_DIR: path.join(evidence, "sessions"), PI_OFFLINE: "1", PI_TELEMETRY: "0", PI_SUBAGENT_PI_BINARY: pi, HOST_PROBE_EVENTS: path.join(evidence, "events.jsonl"), HOST_PROBE_NETWORK_LOG: path.join(evidence, "network.jsonl"), HOST_PROBE_PORT: String(port), NODE_OPTIONS: `--require=${path.join(fixtures, "network-guard.cjs")}` };
write("environment.json", env);
const common = ["--mode", "json", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-mcp", "--provider", "host-probe", "--model", "fixture-a", "--thinking", "off", "--extension", observer];
async function run(name, extra, prompt, cwd = work) {
  const args = [...common, ...extra, prompt];
  write(`${name}.command.json`, { command: pi, args, cwd });
  const child = spawn(pi, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
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

/** 真实 RPC 控制通道：prompt → abort → new_session，全部走宿主协议。 */
async function runRpc(name, extra, cwd = work) {
  const base = [...common];
  base.splice(base.indexOf("--mode"), 2);
  const child = spawn(pi, [...base, "--mode", "rpc", ...extra], { cwd, env, stdio: ["pipe", "pipe", "pipe"] });
  const lines = [];
  const debug = fs.createWriteStream(path.join(evidence, `${name}.stdout.jsonl`));
  const stderr = fs.createWriteStream(path.join(evidence, `${name}.stderr.txt`));
  child.stderr.pipe(stderr);
  let buffer = "";
  const waiters = [];
  child.stdout.on("data", (chunk) => {
    buffer += chunk.toString("utf8");
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (!line.trim()) continue;
      const record = parse(line);
      lines.push(record);
      debug.write(`${line}\n`);
      for (const waiter of [...waiters]) if (waiter.match(record)) { waiters.splice(waiters.indexOf(waiter), 1); waiter.resolve(record); }
    }
  });
  const waitFor = (match, label, timeoutMs = 30000) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`rpc timeout: ${label}`)), timeoutMs);
    waiters.push({ match, resolve: (record) => { clearTimeout(timer); resolve(record); } });
  });
  const send = (record) => child.stdin.write(`${JSON.stringify(record)}\n`);
  const started = waitFor((record) => record.type === "agent_start", "agent_start");
  send({ id: "p1", type: "prompt", message: "HOST_PROBE_RPC: reply slowly." });
  await started;
  const settled = waitFor((record) => record.type === "agent_settled", "agent_settled");
  send({ id: "a1", type: "abort" });
  const afterAbort = await settled;
  const beforeState = lines.filter((record) => record.type === "agent_settled").length;
  send({ id: "s1", type: "new_session" });
  await waitFor((record) => record.type === "response" && record.id === "s1", "new_session response");
  // 新会话里再跑一轮：旧会话的守卫不能再用旧 generation 写状态。
  const secondStart = waitFor((record) => record.type === "agent_start", "second agent_start");
  send({ id: "p2", type: "prompt", message: "HOST_PROBE_RPC: second session." });
  await secondStart;
  await new Promise((resolve) => setTimeout(resolve, 2500));
  child.kill("SIGTERM");
  await new Promise((resolve) => child.on("close", resolve));
  await new Promise((resolve) => stderr.end(resolve));
  await new Promise((resolve) => debug.end(resolve));
  return { lines, afterAbort, beforeState };
}
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
  scenario = "guard";
  const xr = path.join(root, "skills/x-rail/scripts/xr");
  const guardSession = randomUUID();
  const xrEnv = { ...process.env, PI_SESSION_ID: "", XR_SESSION: "" };
  fs.writeFileSync(path.join(work, "README.md"), "guard fixture\n");
  const initRun = spawnSync("python3", [xr, "init", "probe", "--session", guardSession], { cwd: work, encoding: "utf8", env: xrEnv });
  check("guard probe created a bound task run", () => assert.equal(initRun.status, 0, initRun.stdout + initRun.stderr));
  const activeRun = fs.readFileSync(path.join(work, ".work-docs/runs/ACTIVE"), "utf8").trim();
  const runDir = path.join(work, ".work-docs/runs", activeRun);
  env.X_RAIL_XR = xr;
  await run("guard", ["--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts"), "--session-id", guardSession, "--tools", "probe_action,read"], "HOST_PROBE_GUARD: read README.md, then probe_action ok, fail, blocked.");
  const generation = JSON.parse(fs.readFileSync(path.join(runDir, "binding.json"), "utf8")).generation;
  const taskEvents = jsonl(path.join(runDir, "events.jsonl"));
  const detail = (event, key) => event.detail?.[key] ?? event[key];
  const ofType = (type, id) => taskEvents.find((event) => event.type === type && detail(event, "op_id") === id);
  write("guard-events.json", taskEvents.filter((event) => event.type.startsWith("op_")));
  check("guard records tool intent before execution with bound identity", () => {
    assert.equal(generation, 2);
    for (const id of ["probe_read", "probe_ok", "probe_fail"]) {
      const intent = ofType("op_intent", id);
      assert.ok(intent, `missing intent ${id}`);
      assert.equal(intent.session_id, guardSession);
      assert.equal(intent.generation, generation);
      assert.equal(intent.workspace, fs.realpathSync(work));
    }
    assert.equal(detail(ofType("op_intent", "probe_read"), "readonly"), true);
    assert.equal(detail(ofType("op_intent", "probe_ok"), "readonly"), false);
    assert.equal(detail(ofType("op_intent", "probe_ok"), "tool"), "probe_action");
  });
  check("guard pairs success, error and guard-block on real settlement", () => {
    assert.equal(detail(ofType("op_result", "probe_ok"), "outcome"), "success");
    assert.equal(detail(ofType("op_result", "probe_fail"), "outcome"), "error");
    // 别的扩展抢先阻断时 guard 的 tool_call 不再执行，因此没有意图；工具确实没跑，按未开始记录。
    assert.equal(ofType("op_intent", "probe_blocked"), undefined);
    assert.equal(detail(ofType("op_reconcile", "probe_blocked"), "resolution"), "not-started");
    assert.equal(ofType("op_result", "probe_blocked"), undefined);
  });
  check("guard refuses to auto-continue while a tool side effect is unresolved", () => {
    assert.equal(taskEvents.filter((event) => event.type === "resume").length, 0);
    assert.equal(fs.existsSync(path.join(runDir, "handoff.md")), false);
  });
  // 干净 run：没装 x-failover，续跑只能来自守卫自己注册的 agent_before_settle。
  const cont = path.join(evidence, "cont");
  fs.mkdirSync(cont, { recursive: true });
  const contSession = randomUUID();
  spawnSync("python3", [xr, "init", "cont", "--session", contSession], { cwd: cont, encoding: "utf8", env: xrEnv });
  fs.writeFileSync(path.join(cont, "note.md"), "pending\n");
  const added = spawnSync("python3", [xr, "--session", contSession, "plan", "add", "u1", "Pending unit", "--deps", "none", "--files", "note.md", "--verify", "test -f note.md"], { cwd: cont, encoding: "utf8", env: xrEnv });
  check("continuable fixture has one pending unit", () => assert.equal(added.status, 0, added.stdout + added.stderr));
  const contRun = fs.readFileSync(path.join(cont, ".work-docs/runs/ACTIVE"), "utf8").trim();
  const contDir = path.join(cont, ".work-docs/runs", contRun);
  scenario = "cont";
  await run("cont", ["--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts"), "--session-id", contSession], "HOST_PROBE_CONT: reply DONE.", cont);
  const contEvents = jsonl(path.join(contDir, "events.jsonl"));
  check("standalone guard continues without failover, then stops on no progress", () => {
    const resumes = contEvents.filter((event) => event.type === "resume");
    const settled = contEvents.filter((event) => event.type === "settled");
    write("guard-continue.json", { resumes: resumes.length, settled: settled.length });
    assert.equal(resumes.length, 3, `resumes=${resumes.length}`);
    assert.ok(settled.some((event) => event.detail?.boundary?.outcome === "completed"), JSON.stringify(settled.slice(0, 2)));
    assert.ok(!("error" in (settled[0]?.detail ?? {})), "settled detail must not invent an error field");
    assert.match(fs.readFileSync(path.join(contDir, "handoff.md"), "utf8"), /连续 3 次续跑/);
    // 续跑计数存在运行目录里，重开会话不归零。
    const guardMemory = JSON.parse(fs.readFileSync(path.join(contDir, "guard.json"), "utf8"));
    assert.equal(guardMemory.continues, 3);
    assert.ok(guardMemory.stalled >= 2, `stalled=${guardMemory.stalled}`);
  });
  const failDir = path.join(evidence, "failstop");
  fs.mkdirSync(failDir, { recursive: true });
  const failSession = randomUUID();
  spawnSync("python3", [xr, "init", "failstop", "--session", failSession], { cwd: failDir, encoding: "utf8", env: xrEnv });
  const failRun = fs.readFileSync(path.join(failDir, ".work-docs/runs/ACTIVE"), "utf8").trim();
  const failRunDir = path.join(failDir, ".work-docs/runs", failRun);
  // 检查器读不动（表头坏）且 handoff.md 本身是个目录，写入必然失败。
  fs.writeFileSync(path.join(failRunDir, "units.tsv"), "broken\theader\n");
  fs.mkdirSync(path.join(failRunDir, "handoff.md"));
  scenario = "cont";
  await run("failstop", ["--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts"), "--session-id", failSession], "HOST_PROBE_FAILSTOP: reply DONE.", failDir);
  const failExit = JSON.parse(fs.readFileSync(path.join(evidence, "failstop.exit.json"), "utf8"));
  const failEvents = jsonl(path.join(failRunDir, "events.jsonl"));
  check("检查器失败且 handoff 写不下去时停下并记下原因", () => {
    assert.equal(failExit.code, 0, `exit=${JSON.stringify(failExit)}`);
    assert.equal(failEvents.filter((event) => event.type === "resume").length, 0);
    const failed = failEvents.find((event) => event.type === "handoff-failed");
    assert.ok(failed, `no handoff-failed event: ${failEvents.map((event) => event.type).join(",")}`);
    assert.match(String(failed.detail?.reason ?? ""), /检查器/);
    assert.match(String(failed.detail?.error ?? ""), /EISDIR|ENOTDIR|directory|is a directory/i);
  });
  const rpcDir = path.join(evidence, "rpc");
  fs.mkdirSync(rpcDir, { recursive: true });
  const rpcSession = randomUUID();
  spawnSync("python3", [xr, "init", "rpc", "--session", rpcSession], { cwd: rpcDir, encoding: "utf8", env: xrEnv });
  fs.writeFileSync(path.join(rpcDir, "note.md"), "pending\n");
  spawnSync("python3", [xr, "--session", rpcSession, "plan", "add", "u1", "Pending unit", "--deps", "none", "--files", "note.md", "--verify", "test -f note.md"], { cwd: rpcDir, encoding: "utf8", env: xrEnv });
  const rpcRun = fs.readFileSync(path.join(rpcDir, ".work-docs/runs/ACTIVE"), "utf8").trim();
  const rpcRunDir = path.join(rpcDir, ".work-docs/runs", rpcRun);
  scenario = "rpc";
  const rpc = await runRpc("rpc", ["--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts"), "--session-id", rpcSession], rpcDir);
  const rpcEvents = jsonl(path.join(rpcRunDir, "events.jsonl"));
  check("real abort is recorded and does not resume the task", () => {
    assert.equal(rpc.afterAbort.type, "agent_settled");
    const settled = rpcEvents.filter((event) => event.type === "settled");
    assert.ok(settled.length >= 1, "no settled event");
    assert.equal(settled[0].detail.settled.aborted, true, JSON.stringify(settled[0].detail));
    assert.equal(rpcEvents.filter((event) => event.type === "resume").length, 0, "aborted run must not auto-continue");
  });
  check("session switch stops the old session from writing task state", () => {
    // 新会话会重置扩展状态；旧身份既不能续跑也不能继续记账。
    const ids = [...new Set(rpcEvents.map((event) => event.session_id))];
    const binding = JSON.parse(fs.readFileSync(path.join(rpcRunDir, "binding.json"), "utf8"));
    write("rpc-summary.json", { ids, binding, settled: rpcEvents.filter((event) => event.type === "settled").length, total: rpcEvents.length });
    assert.deepEqual(ids, [rpcSession], `old identity wrote after switch: ${ids.join(",")}`);
    assert.equal(binding.session_id, rpcSession, "binding must not be silently changed by the new session");
    assert.equal(rpcEvents.filter((event) => event.type === "resume").length, 0);
    assert.equal(rpcEvents.filter((event) => event.type === "rebind").length, 0);
  });
  const norun = path.join(evidence, "norun");
  fs.mkdirSync(norun, { recursive: true });
  const norunStart = events().length;
  scenario = "norun";
  await run("norun", ["--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts"), "--tools", "read"], "HOST_PROBE_NORUN: reply DONE.", norun);
  check("guard without a run does nothing", () => {
    assert.equal(fs.existsSync(path.join(norun, ".work-docs/runs")), false);
    assert.equal(events().slice(norunStart).filter((event) => event.type === "handoff").length, 0);
    assert.equal(fs.existsSync(path.join(norun, "handoff.md")), false);
  });
  const inspect = spawnSync("python3", [xr, "--run-id", activeRun, "inspect", "--json"], { cwd: work, encoding: "utf8", env: xrEnv });
  write("guard-inspect.json", inspect.stdout);
  check("host did not replay local fixture tools", () => {
    const guardStart = events().find((event) => event.type === "session_start" && event.sessionId === guardSession);
    assert.ok(guardStart, "no guard session_start");
    for (const id of ["probe_ok", "probe_fail"]) {
      const ran = events().filter((event) => event.pid === guardStart.pid && event.type === "execute_enter" && event.toolCallId === id);
      assert.equal(ran.length, 1, `${id} executed ${ran.length} times`);
    }
  });
  check("uncertain tool error blocks completion until reconciled", () => {
    assert.equal(inspect.status, 0, inspect.stdout + inspect.stderr);
    const snapshot = JSON.parse(inspect.stdout);
    assert.deepEqual(snapshot.unresolved_ops, ["probe_fail"]);
    assert.equal(snapshot.done_met, false);
    assert.equal(snapshot.automation_allowed, false);
    assert.ok(snapshot.reasons.includes("unresolved:probe_fail"), JSON.stringify(snapshot.reasons));
  });
  check("reconcile clears the unknown but keeps it out of done", () => {
    const reconcile = spawnSync("python3", [xr, "--run-id", activeRun, "--session", guardSession, "op", "reconcile", "probe_fail", "--resolution", "completed", "--record", "host:probe-verified"], { cwd: work, encoding: "utf8", env: xrEnv });
    assert.equal(reconcile.status, 0, reconcile.stdout + reconcile.stderr);
    const again = JSON.parse(spawnSync("python3", [xr, "--run-id", activeRun, "inspect", "--json"], { cwd: work, encoding: "utf8", env: xrEnv }).stdout);
    assert.deepEqual(again.unresolved_ops, []);
    assert.equal(again.done_met, false);
  });
  scenario = "retry";
  const beforeRetry = requests.length;
  await run("retry", ["--model", "auto"], "HOST_PROBE_RETRY: force a retry and finish");
  const retryRequests = requests.slice(beforeRetry).map((item) => item.body.model);
  const retrySummary = {
    requests: retryRequests,
    retryEvents: events().filter((event) => ["auto_retry_start", "auto_retry_end"].includes(event.type)),
    routeEvents: events().filter((event) => event.type === "route"),
    exit: JSON.parse(fs.readFileSync(path.join(evidence, "retry.exit.json"), "utf8")),
  };
  write("retry-summary.json", retrySummary);
  check("Pi native 503 retry routes to the next physical model", () => {
    assert.deepEqual(retryRequests, ["fixture-a", "fixture-b"]);
    assert.equal(retrySummary.routeEvents.filter((event) => event.reason === "retry").length, 1);
    assert.equal(retrySummary.routeEvents.find((event) => event.reason === "retry")?.selected, "fixture-b");
    assert.ok(retrySummary.routeEvents.find((event) => event.reason === "retry")?.failed?.startsWith("503:"), JSON.stringify(retrySummary, null, 2));
    assert.equal(retrySummary.exit.code, 0);
  });
  scenario = "async";
  const asyncSession = randomUUID();
  const closedGuard = spawnSync("python3", [xr, "--session", guardSession, "close"], { cwd: work, encoding: "utf8", env: xrEnv });
  assert.equal(closedGuard.status, 0, closedGuard.stdout + closedGuard.stderr);
  const asyncInit = spawnSync("python3", [xr, "init", "worker", "--session", asyncSession], { cwd: work, encoding: "utf8", env: xrEnv });
  assert.equal(asyncInit.status, 0, asyncInit.stdout + asyncInit.stderr);
  const asyncRunId = fs.readFileSync(path.join(work, ".work-docs/runs/ACTIVE"), "utf8").trim();
  const asyncRunDir = path.join(work, ".work-docs/runs", asyncRunId);
  for (const args of [["plan", "add", "child", "Local child", "--deps", "none", "--files", "README.md", "--verify", "true", "--kind", "research"], ["next"]]) {
    const result = spawnSync("python3", [xr, "--session", asyncSession, ...args], { cwd: work, encoding: "utf8", env: xrEnv });
    assert.equal(result.status, 0, result.stdout + result.stderr);
  }
  const asyncEvents = await run("async", ["--session-id", asyncSession, "--tools", "subagent", "--extension", path.join(subagents, "index.js"), "--extension", path.join(root, "skills/x-rail/extensions/x-run-guard.ts")], "HOST_PROBE_ASYNC: authorized local fixture subagent");
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
  check("task guard receives the real child terminal result exactly once", () => {
    const taskLog = jsonl(path.join(asyncRunDir, "events.jsonl"));
    const started = taskLog.filter((item) => item.type === "worker_started");
    const received = taskLog.filter((item) => item.type === "worker_received");
    assert.equal(started.length, 1, JSON.stringify(taskLog));
    assert.equal(received.length, 1, JSON.stringify(taskLog));
    assert.equal(started[0].detail.child_run_id, launch.details.runId);
    assert.equal(received[0].detail.child_run_id, launch.details.runId);
    const receipt = JSON.parse(fs.readFileSync(path.join(asyncRunDir, received[0].detail.path), "utf8"));
    assert.deepEqual(receipt.child_sessions, [childExecution.sessionId]);
    const checked = spawnSync("python3", [xr, "inspect", "--json"], { cwd: work, encoding: "utf8", env: xrEnv });
    assert.equal(checked.status, 0, checked.stdout + checked.stderr);
    const snapshot = JSON.parse(checked.stdout);
    assert.deepEqual(snapshot.pending_workers, []);
    assert.equal(snapshot.done_met, false);
    write("async-task-events.json", taskLog);
    write("async-task-inspect.json", snapshot);
  });
  check("parent launch result precedes child completion", () => {
    const childSettled = events().find((event) => event.type === "agent_settled" && event.pid === childExecution?.pid);
    assert.ok(childSettled);
    assert.ok(launch.at < childSettled.at);
  });
  check("all parent invocations exit successfully", () => {
    for (const name of ["basic", "resume", "new", "retry", "async", "guard"]) assert.deepEqual(JSON.parse(fs.readFileSync(path.join(evidence, `${name}.exit.json`))), { code: 0, signal: null });
  });
  check("all Pi processes inherit isolation and connect only to fixture", () => {
    const network = jsonl(env.HOST_PROBE_NETWORK_LOG);
    for (const event of network.filter((item) => item.type === "process")) { assert.equal(event.agentDir, agentDir); assert.equal(event.home, home); assert.equal(event.offline, "1"); }
    const commands = fs.readdirSync(evidence).filter((file) => file.endsWith(".command.json"));
    assert.ok(network.filter((item) => item.type === "process").length >= commands.length, `${network.filter((item) => item.type === "process").length} < ${commands.length}`);
    assert.ok(network.some((item) => item.pid === childExecution?.pid && item.type === "connect"));
    assert.equal(network.filter((item) => item.allowed === false).length, 0);
    assert.ok(requests.every((item) => item.host === `127.0.0.1:${port}` && item.url === "/v1/chat/completions"));
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
