import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { emptyFile, freshBreaker, type BreakerState, type FailoverFile } from "./breaker.ts";
import type { RunMemory } from "./switch.ts";
import { freshMemory } from "./switch.ts";
import { writeAtomic } from "./file-io.ts";

export interface Persisted extends FailoverFile {
  runs: Record<string, RunMemory>;
  boundaryNonce?: string;
}

export function statePath(env: NodeJS.ProcessEnv = process.env, home = os.homedir()): string {
  if (env.X_FAILOVER_STATE) return env.X_FAILOVER_STATE;
  return path.join(home, ".pi", "agent", "state", "x-failover.json");
}

export function loadState(file: string): Persisted {
  try {
    const raw = JSON.parse(fs.readFileSync(file, "utf8")) as Partial<Persisted>;
    return {
      version: 1,
      disabled: raw.disabled === true,
      breakers: raw.breakers && typeof raw.breakers === "object" ? raw.breakers : {},
      runs: raw.runs && typeof raw.runs === "object" ? raw.runs : {},
      boundaryNonce: typeof raw.boundaryNonce === "string" ? raw.boundaryNonce : undefined,
    };
  } catch {
    return { ...emptyFile(), runs: {} };
  }
}

function sleep(): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10);
}

function withLock<T>(file: string, work: () => T): T {
  const lock = `${file}.lock`;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  for (;;) {
    try {
      fs.mkdirSync(lock);
      fs.writeFileSync(path.join(lock, "owner"), `${process.pid}\n${Date.now()}\n`, "utf8");
      break;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      try {
        const [pidText, timeText] = fs.readFileSync(path.join(lock, "owner"), "utf8").split("\n");
        const stale = Date.now() - Number(timeText) > 120_000;
        if (stale) {
          try { process.kill(Number(pidText), 0); } catch { fs.rmSync(lock, { recursive: true, force: true }); }
        }
      } catch { fs.rmSync(lock, { recursive: true, force: true }); }
      sleep();
    }
  }
  try { return work(); } finally { fs.rmSync(lock, { recursive: true, force: true }); }
}

function saveUnlocked(file: string, state: Persisted): void {
  writeAtomic(file, `${JSON.stringify(state, null, 2)}\n`);
}

export function saveState(file: string, state: Persisted): void {
  withLock(file, () => saveUnlocked(file, state));
}

export function updateState(file: string, update: (state: Persisted) => void): Persisted {
  return withLock(file, () => {
    const state = loadState(file);
    update(state);
    saveUnlocked(file, state);
    return state;
  });
}

export function breakerFor(state: Persisted, key: string): BreakerState {
  return state.breakers[key] ?? freshBreaker();
}

export function memoryFor(state: Persisted, runId: string): RunMemory {
  return state.runs[runId] ?? freshMemory();
}
