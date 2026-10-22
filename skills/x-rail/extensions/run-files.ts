import { execFile, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { writeAtomic } from "./file-io.ts";
import { WATCHDOG_GRACE_MS } from "./constants.ts";
import { fileURLToPath } from "node:url";

export interface ActiveRun {
  id: string;
  dir: string;
}

const RUN_ID = /^\d{8}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*(?:-\d+)?$/;

/** 同一工作区的规范路径；xr 侧用 Path.resolve()，撞上符号链接时两边文字才对得上。 */
function realpath(target: string): string {
  try {
    return fs.realpathSync(target);
  } catch {
    return path.resolve(target);
  }
}

export function findActiveRun(cwd: string): ActiveRun | null {
  const root = path.resolve(realpath(cwd), ".work-docs", "runs");
  const pointer = path.join(root, "ACTIVE");
  try {
    const id = fs.readFileSync(pointer, "utf8").trim();
    if (!RUN_ID.test(id)) return null;
    const dir = path.resolve(root, id);
    if (path.dirname(dir) !== root && !dir.startsWith(`${root}${path.sep}`)) return null;
    if (!fs.existsSync(path.join(dir, "RUN.md"))) return null;
    return { id, dir };
  } catch {
    return null;
  }
}

export function appendEvent(dir: string, record: Record<string, unknown>): void {
  const file = path.join(dir, "events.jsonl");
  fs.appendFileSync(file, `${JSON.stringify(record)}\n`, { encoding: "utf8", mode: 0o600 });
}

export function readCapsule(dir: string): string {
  try {
    return fs.readFileSync(path.join(dir, "capsule.md"), "utf8");
  } catch {
    return "";
  }
}

export function unitsFingerprint(dir: string): string {
  const units = readOrEmpty(path.join(dir, "units.tsv"));
  const ledger = readOrEmpty(path.join(dir, "ledger.tsv"));
  return `${units}\n---\n${ledger}`;
}

function readOrEmpty(file: string): string {
  try {
    return fs.readFileSync(file, "utf8");
  } catch {
    return "";
  }
}

export interface RunBinding {
  schema: 1;
  workspace: string;
  run_id: string;
  session_id: string;
  generation: number;
  owner?: string;
  created_at?: string;
  lease: "active" | "paused" | "released";
}

/** 绑定文件坏掉时返回 null，不猜默认值。 */
export function parseBinding(raw: string): RunBinding | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const item = data as Record<string, unknown>;
  if (item.schema !== 1) return null;
  if (typeof item.workspace !== "string" || item.workspace === "") return null;
  if (typeof item.run_id !== "string" || item.run_id === "") return null;
  if (typeof item.session_id !== "string" || item.session_id === "") return null;
  if (typeof item.generation !== "number" || !Number.isInteger(item.generation) || item.generation < 1) return null;
  if (item.lease !== "active" && item.lease !== "paused" && item.lease !== "released") return null;
  return {
    schema: 1,
    workspace: item.workspace,
    run_id: item.run_id,
    session_id: item.session_id,
    generation: item.generation,
    owner: typeof item.owner === "string" ? item.owner : undefined,
    created_at: typeof item.created_at === "string" ? item.created_at : undefined,
    lease: item.lease,
  };
}

export function bindingMatches(
  binding: RunBinding | null,
  expected: { workspace: string; runId: string; sessionId: string; generation?: number },
): boolean {
  if (!binding) return false;
  return binding.workspace === realpath(expected.workspace)
    && binding.run_id === expected.runId
    && binding.session_id === expected.sessionId
    && (expected.generation === undefined || binding.generation === expected.generation);
}

export function readBinding(dir: string): RunBinding | null {
  try {
    return parseBinding(fs.readFileSync(path.join(dir, "binding.json"), "utf8"));
  } catch {
    return null;
  }
}

/** 权威检查结果。字段与 `xr inspect --json` 一一对应。 */
export interface InspectSnapshot {
  mode: "managed" | "legacy" | "invalid";
  phase: string;
  automation_allowed: boolean;
  done_met: boolean;
  ready: string[];
  doing: string[];
  blocked: string[];
  stale_units: string[];
  unresolved_ops: string[];
  pending_workers: string[];
  binding: { session_id: string; generation: number; lease: string };
  receipt_status: "missing" | "valid" | "stale" | "invalid";
  acceptance_status: { total: number; covered: number };
  reasons: string[];
  truncated_tail: boolean;
}

export function validInspectSnapshot(value: unknown, runId: string): value is InspectSnapshot {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  const acceptance = item.acceptance_status;
  const binding = item.binding as Record<string, unknown> | undefined;
  return item.schema_version === 1 && item.run_id === runId
    && ["managed", "legacy", "invalid"].includes(String(item.mode))
    && typeof binding === "object" && binding !== null
    && typeof binding.session_id === "string"
    && typeof binding.generation === "number"
    && typeof binding.lease === "string"
    && typeof item.phase === "string"
    && typeof item.automation_allowed === "boolean"
    && typeof item.done_met === "boolean"
    && ["ready", "doing", "blocked", "stale_units", "unresolved_ops", "pending_workers", "reasons"].every((key) => Array.isArray(item[key]) && (item[key] as unknown[]).every((part) => typeof part === "string"))
    && typeof item.truncated_tail === "boolean"
    && typeof acceptance === "object" && acceptance !== null
    && Number.isInteger((acceptance as Record<string, unknown>).total)
    && Number.isInteger((acceptance as Record<string, unknown>).covered)
    && ["missing", "valid", "stale", "invalid"].includes(String(item.receipt_status));
}

/** 检查器失败一律返回 null：调用方按“暂停”处理，不能当完成。 */
export function inspectRun(cwd: string, runId: string, timeoutMs = 5_000): Promise<InspectSnapshot | null> {
  const bin = xrPath(cwd);
  if (!bin) return Promise.resolve(null);
  return new Promise((resolve) => {
    execFile(
      bin,
      ["--repo", cwd, "--run-id", runId, "inspect", "--json"],
      { timeout: timeoutMs, maxBuffer: 1_000_000 },
      (error, stdout) => {
        if (error) {
          resolve(null);
          return;
        }
        try {
          const parsed: unknown = JSON.parse(stdout);
          resolve(validInspectSnapshot(parsed, runId) ? parsed : null);
        } catch {
          resolve(null);
        }
      },
    );
  });
}

export function xrPath(cwd: string): string | null {
  // 安装后扩展在 <agent-dir>/extensions/x-rail，而 xr 在 <agent-dir>/skills/x-rail/scripts。
  const agentDir = process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".pi", "agent");
  const candidates = [
    process.env.X_RAIL_XR,
    fileURLToPath(new URL("../scripts/xr", import.meta.url)),
    path.join(cwd, "skills", "x-rail", "scripts", "xr"),
    path.join(agentDir, "skills", "x-rail", "scripts", "xr"),
    path.join(os.homedir(), ".pi", "agent", "skills", "x-rail", "scripts", "xr"),
  ].filter((item): item is string => Boolean(item));
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

export function refreshCapsule(identity: HostIdentity): boolean {
  const bin = xrPath(identity.workspace);
  if (!bin) return false;
  try {
    execFileSync(bin, [
      "--repo", identity.workspace, "--run-id", identity.runId,
      "--session", identity.sessionId, "--generation", String(identity.generation),
      "capsule",
    ], { stdio: "ignore", timeout: 5_000 });
    return true;
  } catch {
    // 胶囊失败不能挡住压缩或续跑，但必须让调用方知道没刷新成功。
    return false;
  }
}

/** run 里有 doing 单元且 updated 在宽限窗口内：用于避免落盘瞬间被看门狗误杀。 */
export function runDoingFresh(dir: string, now: number): boolean {
  const lines = readOrEmpty(path.join(dir, "units.tsv")).trim().split("\n").filter(Boolean);
  const header = lines[0]?.split("\t") ?? [];
  const stateAt = header.indexOf("state");
  const updatedAt = header.indexOf("updated");
  if (stateAt < 0 || updatedAt < 0) return false;
  return lines.slice(1).some((line) => {
    const cols = line.split("\t");
    if (cols[stateAt] !== "doing") return false;
    const updated = Date.parse(cols[updatedAt] ?? "");
    return Number.isFinite(updated) && updated <= now && now - updated <= WATCHDOG_GRACE_MS;
  });
}

export function guardMemoryPath(dir: string): string {
  return path.join(dir, "guard.json");
}

export interface GuardMemory {
  continues: number;
  stalled: number;
  fingerprint: string;
  boundaryNonce?: string;
}

export function loadGuardMemory(dir: string): GuardMemory {
  try {
    const raw = JSON.parse(fs.readFileSync(guardMemoryPath(dir), "utf8")) as Partial<GuardMemory>;
    return {
      continues: raw.continues ?? 0,
      stalled: raw.stalled ?? 0,
      fingerprint: raw.fingerprint ?? "",
      boundaryNonce: raw.boundaryNonce,
    };
  } catch {
    return { continues: 0, stalled: 0, fingerprint: "" };
  }
}

/** 写入必须走 xr，保证在运行锁内且带代次校验；扩展不直接改运行目录状态。 */
export function saveGuardMemory(identity: HostIdentity, memory: GuardMemory): boolean {
  const bin = xrPath(identity.workspace);
  if (!bin) return false;
  try {
    execFileSync(bin, [
      "--repo", identity.workspace, "--run-id", identity.runId,
      "--session", identity.sessionId, "--generation", String(identity.generation),
      "guard", "set",
      "--continues", String(memory.continues),
      "--stalled", String(memory.stalled),
      "--fingerprint", memory.fingerprint,
      ...(memory.boundaryNonce ? ["--boundary-nonce", memory.boundaryNonce] : []),
    ], { stdio: "ignore", timeout: 5_000 });
    return true;
  } catch {
    return false;
  }
}

export interface BoundaryMark {
  nonce: string;
  dependsOnReasoning: boolean;
  unrelated: boolean;
  unattended: boolean;
}

export function readBoundary(dir: string): BoundaryMark | null {
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(dir, "pending-boundary.json"), "utf8")) as Partial<BoundaryMark>;
    if (!raw.nonce) return null;
    return {
      nonce: raw.nonce,
      dependsOnReasoning: raw.dependsOnReasoning === true,
      unrelated: raw.unrelated === true,
      unattended: raw.unattended === true,
    };
  } catch {
    return null;
  }
}

export function workerUnit(identity: HostIdentity): string | null {
  const dir = path.join(identity.workspace, ".work-docs", "runs", identity.runId);
  const lines = readOrEmpty(path.join(dir, "units.tsv")).trim().split("\n");
  const header = lines.shift()?.split("\t") ?? [];
  const state = header.indexOf("state");
  const id = header.indexOf("id");
  const doing = lines.map((line) => line.split("\t")).filter((row) => row[state] === "doing");
  return doing.length === 1 ? doing[0][id] ?? null : null;
}

export function receiveWorker(identity: HostIdentity, unit: string, statusPath: string): boolean {
  const bin = xrPath(identity.workspace);
  if (!bin) return false;
  try {
    execFileSync(bin, ["--repo", identity.workspace, "--run-id", identity.runId,
      "--session", identity.sessionId, "--generation", String(identity.generation),
      "receive", unit, "--receipt", statusPath, "--record", "host:terminal-status"],
    { timeout: 5_000, stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

export interface HostIdentity {
  workspace: string;
  runId: string;
  sessionId: string;
  generation: number;
}

/** 经 `xr event` 写入宿主事件；身份、代次与去重由 xr 在运行锁内校验。 */
export function recordHostEvent(
  identity: HostIdentity,
  eventId: string,
  type: string,
  detail: Record<string, unknown>,
): "ok" | "duplicate" | "rejected" | "unavailable" {
  const bin = xrPath(identity.workspace);
  if (!bin) return "unavailable";
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "x-rail-event-"));
  const file = path.join(dir, "record.json");
  try {
    fs.writeFileSync(file, JSON.stringify({
      schema: 1,
      event_id: eventId,
      workspace: realpath(identity.workspace),
      run_id: identity.runId,
      session_id: identity.sessionId,
      generation: identity.generation,
      type,
      detail,
    }), { mode: 0o600 });
    const out = execFileSync(
      bin,
      ["--repo", path.resolve(identity.workspace), "--run-id", identity.runId,
       "--session", identity.sessionId, "--generation", String(identity.generation),
       "event", "--record", file],
      { encoding: "utf8", timeout: 5_000, stdio: ["ignore", "pipe", "pipe"] },
    );
    return out.includes(" duplicate") ? "duplicate" : "ok";
  } catch {
    return "rejected";
  } finally {
    try {
      fs.rmSync(dir, { recursive: true, force: true });
    } catch {
      // 临时目录清理失败不影响已写事件。
    }
  }
}
