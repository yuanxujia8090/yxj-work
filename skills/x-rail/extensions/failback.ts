import { FAILBACK_MAX_CONTEXT_TOKENS, PRIMARY, PROBE_SUCCESSES } from "./constants.ts";
import type { BreakerState } from "./breaker.ts";
import { cooldownElapsed } from "./breaker.ts";
import type { ModelRef } from "./switch.ts";

export type FailbackPolicy = "auto" | "manual" | "never";

export type FailbackAction =
  | { action: "stay"; reason: string }
  | { action: "switch-back"; to: ModelRef; reason: string }
  | { action: "compact-then-switch-back"; to: ModelRef; reason: string };

export interface FailbackInput {
  now: number;
  breaker: BreakerState;
  policy: FailbackPolicy;
  onFallback: boolean;
  unitBoundary: boolean;
  newUserTurn: boolean;
  contextTokens: number | null;
  /** 做不到探活时为 false：冷却结束后在单元边界直接切回。 */
  probeAvailable: boolean;
}

export function decideFailback(input: FailbackInput): FailbackAction {
  const back: ModelRef = { provider: PRIMARY.provider, id: PRIMARY.id };
  if (!input.onFallback) return { action: "stay", reason: "不在兜底模型上" };
  if (input.policy !== "auto") return { action: "stay", reason: `failback=${input.policy}` };
  if (input.breaker.lockedToFallback) return { action: "stay", reason: "切回后 15 分钟内再次熔断，本 run 留在兜底模型" };
  if (!cooldownElapsed(input.breaker, input.now)) return { action: "stay", reason: "冷却未结束" };
  if (input.probeAvailable && input.breaker.consecutiveProbeOk < PROBE_SUCCESSES) {
    return { action: "stay", reason: "探活尚未连续成功 2 次" };
  }
  if (!input.unitBoundary && !input.newUserTurn) return { action: "stay", reason: "不在单元边界或新的用户轮次" };
  if (input.contextTokens === null) return { action: "stay", reason: "上下文大小未知" };
  if (input.contextTokens > FAILBACK_MAX_CONTEXT_TOKENS) {
    return { action: "compact-then-switch-back", to: back, reason: "上下文超过 200K，先压缩再切回" };
  }
  return { action: "switch-back", to: back, reason: "冷却、探活、边界、上下文都满足" };
}
