import {
  BAI_CONTINUE_TOKENS,
  MAX_CONTINUES_PER_RUN,
  MAX_CONTINUES_WITHOUT_PROGRESS,
  OPENAI_CONTINUE_TOKENS,
  SUMMARY_MAX_CHARS,
  IDLE_STOP_MS,
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

/**
 * 一条原则：有产出就继续，连续 `idleMs` 没有任何产出就停。
 * 不区分“模型没吐字”还是“工具没输出”，也不给单个工具设总时长。
 */
export function idleExpired(input: {
  now: number;
  lastProgressAt: number;
  abortedByUser: boolean;
  idleMs?: number;
}): boolean {
  if (input.abortedByUser) return false;
  return input.now - input.lastProgressAt >= (input.idleMs ?? IDLE_STOP_MS);
}
