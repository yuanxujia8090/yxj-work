import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { emptyFile, freshBreaker, type BreakerState, type FailoverFile } from "./breaker.ts";
import type { RunMemory } from "./switch.ts";
import { freshMemory } from "./switch.ts";

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

export function saveState(file: string, state: Persisted): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
  fs.renameSync(tmp, file);
}

export function breakerFor(state: Persisted, key: string): BreakerState {
  return state.breakers[key] ?? freshBreaker();
}

export function memoryFor(state: Persisted, runId: string): RunMemory {
  return state.runs[runId] ?? freshMemory();
}
