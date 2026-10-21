import { execFile, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { writeAtomic } from "./file-io.ts";

export interface ActiveRun {
  id: string;
  dir: string;
}

const RUN_ID = /^\d{8}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*(?:-\d+)?$/;

export function findActiveRun(cwd: string): ActiveRun | null {
  const root = path.resolve(cwd, ".work-docs", "runs");
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
  if (item.lease !== "active" && item.lease !== "paused" && item.lease !== "released") return null;
  return {
    schema: 1,
    workspace: item.workspace,
    run_id: item.run_id,
    session_id: item.session_id,
    owner: typeof item.owner === "string" ? item.owner : undefined,
    created_at: typeof item.created_at === "string" ? item.created_at : undefined,
    lease: item.lease,
  };
}

export function bindingMatches(
  binding: RunBinding | null,
  expected: { workspace: string; runId: string; sessionId: string },
): boolean {
  if (!binding) return false;
  return binding.workspace === path.resolve(expected.workspace)
    && binding.run_id === expected.runId
    && binding.session_id === expected.sessionId;
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
  acceptance_status: { total: number; covered: number };
  reasons: string[];
  truncated_tail: boolean;
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
          resolve(JSON.parse(stdout) as InspectSnapshot);
        } catch {
          resolve(null);
        }
      },
    );
  });
}

export function xrPath(cwd: string): string | null {
  const candidates = [
    process.env.X_RAIL_XR,
    path.join(cwd, "skills", "x-rail", "scripts", "xr"),
    path.join(os.homedir(), ".pi", "agent", "skills", "x-rail", "scripts", "xr"),
  ].filter((item): item is string => Boolean(item));
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

export function refreshCapsule(cwd: string): void {
  const bin = xrPath(cwd);
  if (!bin) return;
  try {
    execFileSync(bin, ["capsule", "--repo", cwd], { stdio: "ignore" });
  } catch {
    // 胶囊失败不能挡住压缩或续跑。
  }
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

export function saveGuardMemory(dir: string, memory: GuardMemory): void {
  writeAtomic(guardMemoryPath(dir), `${JSON.stringify(memory)}\n`);
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
