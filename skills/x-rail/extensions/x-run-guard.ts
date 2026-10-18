import path from "node:path";
import type { AgentBeforeSettleEvent, ExtensionAPI, ExtensionContext, SessionBoundaryDraft } from "@earendil-works/pi-coding-agent";
import { boundaryDecision, compactText, nextStall, renderHandoff, resumeHint, shouldContinue, watchdogDue } from "./guard-core.ts";
import { markWatchdog, takeWatchdog as markWasWatchdog } from "./watchdog.ts";
import {
  appendEvent,
  findActiveRun,
  loadGuardMemory,
  readBoundary,
  readCapsule,
  refreshCapsule,
  runSnapshot,
  saveGuardMemory,
  unitsFingerprint,
} from "./run-files.ts";
import { writeAtomic } from "./file-io.ts";

let lastTokenAt = Date.now();
let userAbort = false;
let activeTools = 0;
let watchdogTimer: ReturnType<typeof setTimeout> | undefined;
let boundRunId: string | null = null;

function bindRunIfNeeded(cwd: string): void {
  const located = findActiveRun(cwd);
  if (located) boundRunId = located.id;
}

export function registerGuardLifecycle(
  pi: ExtensionAPI,
  onWatchdogSettled?: (ctx: ExtensionContext) => Promise<void>,
): void {
  pi.on("session_start", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    boundRunId = located?.id ?? null;
    const hint = resumeHint(located?.id ?? null);
    if (hint) ctx.ui.notify(hint, "info");
  });
  pi.on("message_update", async () => { lastTokenAt = Date.now(); });
  pi.on("provider_stream_event", async () => { lastTokenAt = Date.now(); });
  pi.on("tool_execution_start", async () => { activeTools += 1; lastTokenAt = Date.now(); });
  pi.on("tool_execution_update", async () => { lastTokenAt = Date.now(); });
  pi.on("tool_execution_end", async () => { activeTools = Math.max(0, activeTools - 1); lastTokenAt = Date.now(); });
  pi.on("agent_start", async (_event, ctx) => {
    bindRunIfNeeded(ctx.cwd);
    userAbort = false;
    activeTools = 0;
    lastTokenAt = Date.now();
    if (watchdogTimer) clearTimeout(watchdogTimer);
    const arm = () => {
      watchdogTimer = setTimeout(() => {
        if (activeTools > 0) { lastTokenAt = Date.now(); arm(); return; }
        if (watchdogDue(lastTokenAt, Date.now(), userAbort)) { markWatchdog(); ctx.abort(); return; }
        arm();
      }, 5_000);
    };
    arm();
  });
  pi.on("agent_settled", async (event, ctx) => {
    if (watchdogTimer) clearTimeout(watchdogTimer);
    if (event.aborted && markWasWatchdog()) {
      await onWatchdogSettled?.(ctx);
      return;
    }
    if (event.aborted) userAbort = true;
  });
  pi.on("session_before_compact", async (event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    if (!located) return;
    refreshCapsule(ctx.cwd);
    const capsule = readCapsule(located.dir) || `run ${located.id}：胶囊缺失，先执行 xr capsule。`;
    appendEvent(located.dir, { type: "compaction", supplement: false, ts: new Date().toISOString() });
    return { compaction: {
      summary: compactText(capsule, null),
      firstKeptEntryId: event.preparation.firstKeptEntryId,
      tokensBefore: event.preparation.tokensBefore,
    } };
  });
}

export async function guardBoundary(event: AgentBeforeSettleEvent, ctx: ExtensionContext): Promise<{
  continue: true;
  entries: SessionBoundaryDraft[];
} | undefined> {
  bindRunIfNeeded(ctx.cwd);
  const located = findActiveRun(ctx.cwd);
  if (!located || process.env.X_RAIL_SUBAGENT === "1" || boundRunId !== located.id) return;
  if (event.outcome === "completed" && asksUser(event)) return;
  const snap = runSnapshot(located.dir);
  const memory = loadGuardMemory(located.dir);
  const fingerprint = unitsFingerprint(located.dir);
  const stalled = memory.continues === 0 ? 0 : nextStall(memory.fingerprint, fingerprint, memory.stalled);
  const decision = shouldContinue({
    outcome: event.outcome,
    run: { id: located.id, active: true, doneMet: snap.doneMet, allBlockedByGate: snap.allBlockedByGate,
      fingerprint, continues: memory.continues, stalledFingerprints: stalled },
  });
  if (decision.action === "ignore") return;
  if (decision.action === "stop") {
    if (decision.handoff) {
      writeAtomic(path.join(located.dir, "handoff.md"), renderHandoff(located.id, decision.reason));
      appendEvent(located.dir, { type: "handoff", reason: decision.reason, ts: new Date().toISOString() });
    }
    ctx.ui.notify(decision.reason, "warning");
    return;
  }
  refreshCapsule(ctx.cwd);
  const mark = readBoundary(located.dir);
  const choice = boundaryDecision({
    contextTokens: ctx.getContextUsage()?.tokens ?? null,
    provider: ctx.model?.provider ?? "openai26",
  });
  if (mark && mark.nonce !== memory.boundaryNonce) {
    appendEvent(located.dir, { type: "boundary", choice, ts: new Date().toISOString(), nonce: mark.nonce });
    memory.boundaryNonce = mark.nonce;
  }
  saveGuardMemory(located.dir, { continues: memory.continues + 1, stalled, fingerprint, boundaryNonce: memory.boundaryNonce });
  appendEvent(located.dir, { type: "resume", ts: new Date().toISOString() });
  const entries: SessionBoundaryDraft[] = [];
  if (choice === "compact") {
    const capsule = readCapsule(located.dir) || `run ${located.id}：胶囊缺失，先执行 xr capsule。`;
    entries.push({ type: "compaction", summary: compactText(capsule, null), firstKeptEntryId: null });
  }
  entries.push({ type: "custom_message", customType: "x-run-guard", content: decision.message, display: true });
  return { continue: true, entries };
}

function asksUser(event: AgentBeforeSettleEvent): boolean {
  const messages = event.context?.contextMessages ?? [];
  const last = [...messages].reverse().find((item) => (item as { role?: string }).role === "assistant") as { content?: unknown } | undefined;
  const text = Array.isArray(last?.content)
    ? last.content.filter((item): item is { type: "text"; text: string } => typeof item === "object" && item !== null && (item as { type?: string }).type === "text" && typeof (item as { text?: unknown }).text === "string").map((item) => item.text).join("\n")
    : typeof last?.content === "string" ? last.content : "";
  return /[？?]\s*$/.test(text.trim()) || /请(?:你|用户)?(?:确认|选择|决定|提供|回答|拍板)/.test(text);
}
