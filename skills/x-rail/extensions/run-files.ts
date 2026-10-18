import { execFileSync } from "node:child_process";
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

export function runSnapshot(dir: string): {
  doneMet: boolean;
  allBlockedByGate: boolean;
} {
  const units = readOrEmpty(path.join(dir, "units.tsv")).trim().split("\n").slice(1).filter(Boolean);
  const rows = units.map((line) => line.split("\t"));
  const states = rows.map((cols) => cols[2] ?? "");
  const open = states.filter((state) => state !== "done" && state !== "abandoned");
  const doneMet = rows.length > 0 && open.length === 0;
  const gates = readOrEmpty(path.join(dir, "gates.md"));
  const gateOpen = /status: open/.test(gates);
  const allBlockedByGate = gateOpen && open.length > 0 && open.every((state) => state === "blocked");
  return { doneMet, allBlockedByGate };
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
