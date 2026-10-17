import { COOLDOWN_MAX_MS, COOLDOWN_MIN_MS, E2_THRESHOLD, E2_WINDOW_MS, HYSTERESIS_MS } from "./constants.ts";
import type { ErrorClass } from "./classify.ts";

export interface BreakerState {
  open: boolean;
  openCount: number;
  openedAt: number | null;
  cooldownMs: number;
  e2Times: number[];
  lastFailbackAt: number | null;
  lockedToFallback: boolean;
  consecutiveProbeOk: number;
}

export interface FailoverFile {
  version: 1;
  disabled: boolean;
  breakers: Record<string, BreakerState>;
}

export function freshBreaker(): BreakerState {
  return {
    open: false,
    openCount: 0,
    openedAt: null,
    cooldownMs: COOLDOWN_MIN_MS,
    e2Times: [],
    lastFailbackAt: null,
    lockedToFallback: false,
    consecutiveProbeOk: 0,
  };
}

export function emptyFile(): FailoverFile {
  return { version: 1, disabled: false, breakers: {} };
}

function open(state: BreakerState, now: number): BreakerState {
  const nextCount = state.openCount + 1;
  const cooldownMs = nextCount <= 1 ? COOLDOWN_MIN_MS : Math.min(state.cooldownMs * 2, COOLDOWN_MAX_MS);
  const locked =
    state.lockedToFallback ||
    (state.lastFailbackAt !== null && now - state.lastFailbackAt < HYSTERESIS_MS);
  return {
    ...state,
    open: true,
    openCount: nextCount,
    openedAt: now,
    cooldownMs,
    lockedToFallback: locked,
    consecutiveProbeOk: 0,
  };
}

/** 纯函数。E1/E3/E5 立刻打开；10 分钟内 3 次 E2 打开。 */
export function observe(state: BreakerState, klass: ErrorClass, now: number): { state: BreakerState; opened: boolean } {
  if (klass === "E1" || klass === "E3" || klass === "E5") {
    const next = open(state, now);
    return { state: next, opened: true };
  }
  if (klass === "E2") {
    const e2Times = [...state.e2Times, now].filter((ts) => now - ts <= E2_WINDOW_MS);
    let next: BreakerState = { ...state, e2Times };
    let opened = false;
    if (e2Times.length >= E2_THRESHOLD) {
      next = open(next, now);
      opened = true;
    }
    return { state: next, opened };
  }
  return { state, opened: false };
}

export function cooldownElapsed(state: BreakerState, now: number): boolean {
  return state.open && state.openedAt !== null && now >= state.openedAt + state.cooldownMs;
}

export function noteProbe(state: BreakerState, ok: boolean): BreakerState {
  if (!ok) return { ...state, consecutiveProbeOk: 0 };
  return { ...state, consecutiveProbeOk: state.consecutiveProbeOk + 1 };
}

export function noteFailback(state: BreakerState, now: number): BreakerState {
  return { ...state, open: false, lastFailbackAt: now, consecutiveProbeOk: 0, e2Times: [] };
}

export function anyOpen(file: FailoverFile): boolean {
  return Object.values(file.breakers).some((item) => item.open);
}
