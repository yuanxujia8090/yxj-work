import {
  BAI_CONTINUE_TOKENS,
  MAX_CONTINUES_PER_RUN,
  MAX_CONTINUES_WITHOUT_PROGRESS,
  TOOL_MAX_MS,
  WATCHDOG_GRACE_MS,
  OPENAI_CONTINUE_TOKENS,
  SUMMARY_MAX_CHARS,
  WATCHDOG_MS,
} from "./constants.ts";

export interface GuardRun {
  id: string;
  active: boolean;
  doneMet: boolean;
  allBlockedByGate: boolean;
  fingerprint: string;
  continues: number;
  stalledFingerprints: number;
}

export type ContinueDecision =
  | { action: "continue"; message: string }
  | { action: "stop"; reason: string; handoff: boolean }
  | { action: "ignore"; reason: string };

export function shouldContinue(input: {
  outcome: "completed" | "aborted" | "error";
  run: GuardRun | null;
}): ContinueDecision {
  if (input.outcome === "aborted") return { action: "ignore", reason: "用户中止" };
  if (input.outcome === "error") return { action: "ignore", reason: "provider 错误交给 x-failover" };
  const run = input.run;
  if (!run || !run.active) return { action: "ignore", reason: "没有 active run" };
  if (run.doneMet) return { action: "ignore", reason: "Done 判据已满足" };
  if (run.allBlockedByGate) return { action: "stop", reason: "剩余单元都被 gate 挡住", handoff: true };
  if (run.continues >= MAX_CONTINUES_PER_RUN) return { action: "stop", reason: "续跑次数到上限", handoff: true };
  if (run.stalledFingerprints >= MAX_CONTINUES_WITHOUT_PROGRESS) {
    return { action: "stop", reason: "连续 3 次续跑后 units 和 ledger 都没有变化", handoff: true };
  }
  return {
    action: "continue",
    message: `[x-run-guard] 继续 run ${run.id}。先读 capsule.md，再执行 xr status，从 doing 单元接着做。不要向用户要“继续”。`,
  };
}

/** 续跑之后指纹没变就 +1，变了就归零。 */
export function nextStall(previousFingerprint: string, fingerprint: string, stalled: number): number {
  if (previousFingerprint === fingerprint) return stalled + 1;
  return 0;
}

export function renderHandoff(runId: string, reason: string): string {
  return [
    `# handoff ${runId}`,
    "",
    `阻塞：${reason}`,
    "",
    "已完成和未完成以 units.tsv 和 ledger.tsv 为准，这里不抄表。",
    "",
    "下一条命令：",
    "",
    "```",
    "xr status",
    "```",
    "",
    "恢复：读 capsule.md，再执行 xr status；不要重做已有 VERIFIED 单元。",
    "",
  ].join("\n");
}

export type BoundaryChoice = "continue" | "compact";

export function boundaryDecision(input: {
  contextTokens: number | null;
  provider: string;
}): BoundaryChoice {
  const limit = input.provider === "bai" ? BAI_CONTINUE_TOKENS : OPENAI_CONTINUE_TOKENS;
  return input.contextTokens !== null && input.contextTokens <= limit ? "continue" : "compact";
}

export function compactText(capsule: string, supplement: string | null): string {
  const extra = supplement ? supplement.slice(0, SUMMARY_MAX_CHARS) : "";
  const body = extra ? `${capsule.trim()}\n\n## 对话要点\n\n${extra}` : capsule.trim();
  return body;
}

export function resumeHint(runId: string | null): string | null {
  if (!runId) return null;
  return `有未完成的 run ${runId}。先读 .work-docs/runs/${runId}/capsule.md，再执行 xr status。`;
}

export interface WatchdogInput {
  now: number;
  lastTokenAt: number;
  abortedByUser: boolean;
  /** 每个正在执行的工具已跑了多久（毫秒）。 */
  toolAges: number[];
  /** run 里有 doing 单元，且 updated 落在宽限窗口内。 */
  runDoingFresh: boolean;
  graceUsed: boolean;
}

/** wait=继续等；grace=任务在推进，宽限一次；abort=真挂起；skip=用户已中止。 */
export type WatchdogAction = "wait" | "grace" | "abort" | "skip";

export function watchdogDecision(input: WatchdogInput): WatchdogAction {
  if (input.abortedByUser) return "skip";
  if (input.now - input.lastTokenAt < WATCHDOG_MS) return "wait";
  // 工具在跑：长构建、长测试、同步子代理都归这里，不误杀。
  // 用最老的工具判断：只要有一个工具超过上限就视为挂起，避免“新工具不断续命”。
  if (input.toolAges.length > 0 && Math.max(...input.toolAges) < TOOL_MAX_MS) return "wait";
  if (input.toolAges.length > 0) return "abort";
  // 没有工具，但任务单元刚更新过：给一次宽限，避免刚好在落盘时被中止。
  if (input.runDoingFresh && !input.graceUsed) return "grace";
  return "abort";
}

export function watchdogDue(lastTokenAt: number, now: number, abortedByUser: boolean): boolean {
  if (abortedByUser) return false;
  return now - lastTokenAt >= WATCHDOG_MS;
}
