import path from "node:path";
import { execFileSync } from "node:child_process";
import type { AgentBeforeSettleEvent, ExtensionAPI, ExtensionContext, SessionBoundaryDraft } from "@earendil-works/pi-coding-agent";
import { boundaryDecision, compactText, nextStall, renderHandoff, resumeHint, shouldContinue, watchdogDue } from "./guard-core.ts";
import { markWatchdog, takeWatchdog as markWasWatchdog } from "./watchdog.ts";
import {
  appendEvent,
  bindingMatches,
  findActiveRun,
  inspectRun,
  loadGuardMemory,
  readBinding,
  readBoundary,
  readCapsule,
  refreshCapsule,
  saveGuardMemory,
  unitsFingerprint,
  xrPath,
  type InspectSnapshot,
  type RunBinding,
} from "./run-files.ts";
import { writeAtomic } from "./file-io.ts";

let lastTokenAt = Date.now();
let userAbort = false;
let activeTools = 0;
let watchdogTimer: ReturnType<typeof setTimeout> | undefined;

/** 会话开始时绑定一次，之后不再重读 ACTIVE。 */
let bound: { runId: string; sessionId: string; dir: string } | null = null;

export function currentBinding(): { runId: string; sessionId: string; dir: string } | null {
  return bound;
}

function bindRun(cwd: string, runId: string, sessionId: string): RunBinding | null {
  const bin = xrPath(cwd);
  if (!bin) return null;
  try {
    execFileSync(bin, ["--repo", cwd, "--run-id", runId, "bind", "--session", sessionId], {
      stdio: "ignore",
      timeout: 5_000,
    });
  } catch {
    // 被其他会话占用或绑定失败：保持未绑定，由调用方决定是否提示。
  }
  return readBinding(path.join(path.resolve(cwd, ".work-docs", "runs"), runId));
}

export function registerGuardLifecycle(
  pi: ExtensionAPI,
  onWatchdogSettled?: (ctx: ExtensionContext) => Promise<void>,
): void {
  pi.on("session_start", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    const sessionId = ctx.sessionManager.getSessionId();
    bound = null;
    if (located) {
      const binding = bindRun(ctx.cwd, located.id, sessionId);
      if (bindingMatches(binding, { workspace: ctx.cwd, runId: located.id, sessionId })) {
        bound = { runId: located.id, sessionId, dir: located.dir };
      } else if (binding && binding.lease === "active") {
        ctx.ui.notify(`运行 ${located.id} 被会话 ${binding.session_id} 占用，本会话不自动续跑。`, "warning");
      } else {
        ctx.ui.notify(`运行 ${located.id} 绑定失败（lease=${binding?.lease ?? "missing"}），不自动续跑。`, "warning");
      }
    }
    const hint = resumeHint(bound?.runId ?? null);
    if (hint) ctx.ui.notify(hint, "info");
  });
  pi.on("message_update", async () => { lastTokenAt = Date.now(); });
  pi.on("provider_stream_event", async () => { lastTokenAt = Date.now(); });
  pi.on("tool_execution_start", async () => { activeTools += 1; lastTokenAt = Date.now(); });
  pi.on("tool_execution_update", async () => { lastTokenAt = Date.now(); });
  pi.on("tool_execution_end", async () => { activeTools = Math.max(0, activeTools - 1); lastTokenAt = Date.now(); });
  pi.on("agent_start", async (_event, ctx) => {
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
    if (!bound) return;
    refreshCapsule(ctx.cwd);
    const capsule = readCapsule(bound.dir) || `run ${bound.runId}：胶囊缺失，先执行 xr capsule。`;
    appendEvent(bound.dir, { type: "compaction", supplement: false, ts: new Date().toISOString() });
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
  if (process.env.X_RAIL_SUBAGENT === "1" || !bound) return;
  const located = findActiveRun(ctx.cwd);
  if (located && located.id !== bound.runId) {
    // ACTIVE 被改到别的运行：只提示，不跟着换任务。
    appendEvent(bound.dir, {
      type: "binding-drift",
      expected: bound.runId,
      pointer: located.id,
      ts: new Date().toISOString(),
    });
    ctx.ui.notify(`当前指针指向 ${located.id}，本会话绑定 ${bound.runId}，不自动接管。`, "warning");
    return;
  }
  if (event.outcome === "completed" && asksUser(event)) return;
  const snap = await inspectRun(ctx.cwd, bound.runId);
  if (!snap || snap.mode !== "managed") {
    const why = !snap ? "检查器无结果或超时" : `运行模式 ${snap.mode}：${snap.reasons.join(",") || "不可自动续跑"}`;
    writeAtomic(path.join(bound.dir, "handoff.md"), renderHandoff(bound.runId, why));
    appendEvent(bound.dir, { type: "handoff", reason: why, ts: new Date().toISOString() });
    ctx.ui.notify(`停止自动续跑：${why}`, "warning");
    return;
  }
  const memory = loadGuardMemory(bound.dir);
  const fingerprint = unitsFingerprint(bound.dir);
  const stalled = memory.continues === 0 ? 0 : nextStall(memory.fingerprint, fingerprint, memory.stalled);
  const decision = shouldContinue({
    outcome: event.outcome,
    run: {
      id: bound.runId,
      active: snap.automation_allowed,
      doneMet: snap.done_met,
      allBlockedByGate: allBlockedByGate(snap),
      fingerprint,
      continues: memory.continues,
      stalledFingerprints: stalled,
    },
  });
  if (decision.action === "ignore") return;
  if (decision.action === "stop") {
    if (decision.handoff) {
      writeAtomic(path.join(bound.dir, "handoff.md"), renderHandoff(bound.runId, decision.reason));
      appendEvent(bound.dir, { type: "handoff", reason: decision.reason, ts: new Date().toISOString() });
    }
    ctx.ui.notify(decision.reason, "warning");
    return;
  }
  refreshCapsule(ctx.cwd);
  const mark = readBoundary(bound.dir);
  const choice = boundaryDecision({
    contextTokens: ctx.getContextUsage()?.tokens ?? null,
    provider: ctx.model?.provider ?? "openai26",
  });
  if (mark && mark.nonce !== memory.boundaryNonce) {
    appendEvent(bound.dir, { type: "boundary", choice, ts: new Date().toISOString(), nonce: mark.nonce });
    memory.boundaryNonce = mark.nonce;
  }
  saveGuardMemory(bound.dir, { continues: memory.continues + 1, stalled, fingerprint, boundaryNonce: memory.boundaryNonce });
  appendEvent(bound.dir, { type: "resume", ts: new Date().toISOString() });
  const entries: SessionBoundaryDraft[] = [];
  if (choice === "compact") {
    const capsule = readCapsule(bound.dir) || `run ${bound.runId}：胶囊缺失，先执行 xr capsule。`;
    entries.push({ type: "compaction", summary: compactText(capsule, null), firstKeptEntryId: null });
  }
  entries.push({ type: "custom_message", customType: "x-run-guard", content: decision.message, display: true });
  return { continue: true, entries };
}

/** 没有可做的事且剩余全部被 gate 挡住时才停；放弃单元不算“被挡住”。 */
function allBlockedByGate(snap: InspectSnapshot): boolean {
  return snap.doing.length === 0 && snap.ready.length === 0 && snap.blocked.length > 0;
}

function asksUser(event: AgentBeforeSettleEvent): boolean {
  const messages = event.context?.contextMessages ?? [];
  const last = [...messages].reverse().find((item) => (item as { role?: string }).role === "assistant") as { content?: unknown } | undefined;
  const text = Array.isArray(last?.content)
    ? last.content.filter((item): item is { type: "text"; text: string } => typeof item === "object" && item !== null && (item as { type?: string }).type === "text" && typeof (item as { text?: unknown }).text === "string").map((item) => item.text).join("\n")
    : typeof last?.content === "string" ? last.content : "";
  return /请(?:你|用户)?(?:确认|选择|决定|提供|回答|拍板)/.test(text);
}
