import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const script = path.join(root, "skills/x-rail/extensions/mock26.mjs");
const errors = [
  { status: 503, body: { error: { message: "账号池暂无可用账号" } } },
  { status: 429, body: { error: { message: "gateway_concurrency_limit" } } },
  { status: 503, body: { error: { message: "The service is busy" } } },
  { status: 504, body: { error: { message: "Request timed out." } } },
  { status: 524, body: { error: { message: "HTTP 524" } } },
  { status: 422, body: { error: { message: "unknown variant 'developer'" } } },
];

const child = spawn(process.execPath, [script], {
  env: { ...process.env, MOCK26_SCRIPT: JSON.stringify(errors) },
  stdio: ["ignore", "pipe", "inherit"],
});
const port = await new Promise((resolve, reject) => {
  let buffer = "";
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    const line = buffer.split("\n").find(Boolean);
    if (line) resolve(JSON.parse(line).port);
  });
  child.on("exit", (code) => reject(new Error(`mock26 提前退出 ${code}`)));
});

try {
  for (const step of errors) {
    const response = await fetch(`http://127.0.0.1:${port}/v1/chat/completions`, { method: "POST", body: "{}" });
    const body = await response.json();
    assert.equal(response.status, step.status);
    assert.equal(body.error.message, step.body.error.message);
  }
  console.log("mock26 tests passed");
} finally {
  child.kill();
}
