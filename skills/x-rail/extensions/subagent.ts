import { FALLBACK, READER_LIMIT, TOTAL_LIMIT, WRITER_LIMIT } from "./constants.ts";

export interface Concurrency {
  readers: number;
  writers: number;
  total: number;
}

/** 熔断打开时合计减半（至少 1），写入降到 1。 */
export function concurrencyLimits(breakerOpen: boolean): Concurrency {
  if (!breakerOpen) return { readers: READER_LIMIT, writers: WRITER_LIMIT, total: TOTAL_LIMIT };
  const total = Math.max(1, Math.floor(TOTAL_LIMIT / 2));
  return { readers: Math.min(READER_LIMIT, total), writers: 1, total };
}

export function dispatchModel(breakerOpen: boolean): { model: string; thinking: "high" } | { model: "primary"; thinking: "high" } {
  if (breakerOpen) return { model: `${FALLBACK.provider}/${FALLBACK.id}`, thinking: "high" };
  return { model: "primary", thinking: "high" };
}

/** 实现跑在 bai 上时，评审优先用 openai26。两边都熔断则同家族，并在 ledger 里标记。 */
export function reviewerFamily(implOnFallback: boolean, primaryBreakerOpen: boolean): { model: string; sameFamily: boolean } {
  if (!implOnFallback) return { model: `${FALLBACK.provider}/${FALLBACK.id}`, sameFamily: false };
  if (!primaryBreakerOpen) return { model: "openai26/gpt-6.1-sol", sameFamily: false };
  return { model: `${FALLBACK.provider}/${FALLBACK.id}`, sameFamily: true };
}
