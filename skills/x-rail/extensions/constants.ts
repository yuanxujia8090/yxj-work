/** 04 与 03 里已经拍板的数字。改这里要同时改 xr 和阶段卡。 */

export const PRIMARY = { provider: "openai26", id: "gpt-6.1-sol" } as const;
export const FALLBACK = { provider: "bai", id: "deepseek-v4.1-flash", thinking: "high" as const };
export const SUMMARY_MODEL = { provider: "bai", id: "deepseek-v4.1-flash", thinking: "low" as const };

export const COOLDOWN_MIN_MS = 15 * 60 * 1000;
export const COOLDOWN_MAX_MS = 60 * 60 * 1000;
export const E2_WINDOW_MS = 10 * 60 * 1000;
export const E2_THRESHOLD = 3;
export const E2_RETRY_WAIT_MS = 20_000;
export const HYSTERESIS_MS = 15 * 60 * 1000;
export const PROBE_SUCCESSES = 2;
export const MAX_FAILOVERS_PER_RUN = 8;
export const MAX_FAILOVERS_WITHOUT_PROGRESS = 2;
export const FAILBACK_MAX_CONTEXT_TOKENS = 200_000;
export const OPENAI_CONTINUE_TOKENS = 160_000;
export const BAI_CONTINUE_TOKENS = 350_000;
export const SUMMARY_TIMEOUT_MS = 120_000;
export const SUMMARY_MAX_CHARS = 3_000;
export const CAPSULE_MAX_BYTES = 2_048;
export const WATCHDOG_MS = 180_000;
/** 工具超过这个时长仍没结束，视为挂起，不再无限豁免看门狗。 */
export const TOOL_MAX_MS = 50 * 60_000;
/** 任务单元刚开始推进时，看门狗到期后只宽限这一次。 */
export const WATCHDOG_GRACE_MS = 60_000;
export const MAX_CONTINUES_WITHOUT_PROGRESS = 3;
export const MAX_CONTINUES_PER_RUN = 200;

export const READER_LIMIT = 5;
export const WRITER_LIMIT = 2;
export const TOTAL_LIMIT = 5;
export const SUBAGENT_UNIT_THRESHOLD = 5;

export function modelKey(provider: string, id: string): string {
  return `${provider}/${id}`;
}
