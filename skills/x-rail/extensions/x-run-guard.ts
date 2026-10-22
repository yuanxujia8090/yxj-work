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
  recordHostEvent,
  refreshCapsule,
  saveGuardMemory,
  unitsFingerprint,
  xrPath,
  type HostIdentity,
  type InspectSnapshot,
  type RunBinding,
} from "./run-files.ts";
import { registerHostEvents } from "./host-events.ts";
import { writeAtomic } from "./file-io.ts";
import { randomUUID } from "node:crypto";

let lastTokenAt = Date.now();
let userAbort = false;
let activeTools = 0;
let watchdogTimer: ReturnType<typeof setTimeout> | undefined;
/** 宿主实际报告的边界结局，只用于记录，不猜测缺失字段。 */
let lastOutcome: { outcome: string; aborted: boolean } | null = null;

/** 会话开始时绑定一次，之后不再重读 ACTIVE。 */
let bound: { runId: string; sessionId: string; generation: number; dir: string } | null = null;

export function currentBinding(): { runId: string; sessionId: string; generation: number; dir: string } | null {
  return bound;
}

export function boundIdentity(): HostIdentity | null {
  return bound
    ? { workspace: path.dirname(path.dirname(path.dirname(bound.dir))), runId: bound.runId, sessionId: bound.sessionId, generation: bound.generation }
    : null;
}

/** 事件归属当前绑定；代次过期由 xr 拒绝并返回 rejected。 */
function guardEvent(kind: string, detail: Record<string, unknown>): void {
  const identity = boundIdentity();
  if (!identity) return;
  recordHostEvent(identity, `${kind}-${Date.now()}-${randomUUID()}`, kind, detail);
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
  registerHostEvents(pi, boundIdentity);
  pi.on("session_start", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    const sessionId = ctx.sessionManager.getSessionId();
    bound = null;
    if (located) {
      const binding = bindRun(ctx.cwd, located.id, sessionId);
      if (bindingMatches(binding, { workspace: ctx.cwd, runId: located.id, sessionId }) && binding) {
        bound = { runId: located.id, sessionId, generation: binding.generation, dir: located.dir };
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
    // 新会话/切会话不会重发 session_start：开工前核对身份，变了就重新绑定并递增 generation。
    const sessionId = ctx.sessionManager.getSessionId();
    if (bound && bound.sessionId !== sessionId) {
      const runId = bound.runId;
      const dir = bound.dir;
      const previous = { runId, sessionId: bound.sessionId, generation: bound.generation };
      const binding = bindRun(ctx.cwd, runId, sessionId);
      if (binding && bindingMatches(binding, { workspace: ctx.cwd, runId, sessionId })) {
        bound = { runId, sessionId, generation: binding.generation, dir };
        guardEvent("rebind", { previous, generation: binding.generation });
      } else {
        bound = null;
        ctx.ui.notify(`会话切换后重新绑定失败（lease=${binding?.lease ?? "missing"}），本会话不自动续跑。`, "warning");
      }
    }
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
    // AgentSettledEvent 只带 aborted；outcome 只能取 before_settle 实际保存的值，不能猜。
    const settled = { aborted: event.aborted === true };
    const boundary = lastOutcome;
    lastOutcome = null;
    guardEvent("settled", { settled, boundary });
    if (event.aborted && markWasWatchdog()) {
      await onWatchdogSettled?.(ctx);
      return;
    }
    if (event.aborted) userAbort = true;
  });
  pi.on("agent_before_settle", async (event, ctx) => {
    lastOutcome = { outcome: String(event.outcome ?? "unknown"), aborted: userAbort };
    return guardBoundary(event, ctx);
  });
  pi.on("session_before_compact", async (event, ctx) => {
    if (!bound) return;
    // 不覆盖宿主摘要：只刷新胶囊并记录，摘要仍由 Pi 生成，胶囊留作补充。
    const refreshed = refreshCapsule(ctx.cwd);
    guardEvent("compaction", { supplement: false, capsule: refreshed, firstKeptEntryId: event.preparation.firstKeptEntryId });
  });
}

/** 独立入口：不依赖 failover 扩展，单独加载也能工作。 */
export default function (pi: ExtensionAPI): void {
  registerGuardLifecycle(pi);
}

export async function guardBoundary(event: AgentBeforeSettleEvent, ctx: ExtensionContext): Promise<{
  continue: true | false;
  entries: SessionBoundaryDraft[];
} | undefined> {
  if (process.env.X_RAIL_SUBAGENT === "1" || !bound) return;
  const inherited = event.entries ?? [];
  const located = findActiveRun(ctx.cwd);
  if (located && located.id !== bound.runId) {
    // ACTIVE 被改到别的运行：只提示，不跟着换任务。
    guardEvent("binding-drift", {
      expected: bound.runId,
      pointer: located.id,
    });
    ctx.ui.notify(`当前指针指向 ${located.id}，本会话绑定 ${bound.runId}，不自动接管。`, "warning");
    return;
  }
  if (event.outcome === "completed" && asksUser(event)) return;
  const snap = await inspectRun(ctx.cwd, bound.runId);
  if (!snap || snap.mode !== "managed") {
    const why = !snap ? "检查器无结果或超时" : `运行模式 ${snap.mode}：${snap.reasons.join(",") || "不可自动续跑"}`;
    return stopWithHandoff(ctx, inherited, why);
  }
  // 被接管或换过代次：旧会话不得继续推进，也不写状态。
  if (snap.binding.session_id !== bound.sessionId || snap.binding.generation !== bound.generation) {
    guardEvent("stale-binding", { bound: bound.generation, current: snap.binding.generation });
    ctx.ui.notify(`本会话代次已失效（${bound.generation} → ${snap.binding.generation}），停止自动续跑。`, "warning");
    bound = null;
    return;
  }
  if (snap.pending_workers.length > 0) {
    // 子代理还在跑：不重复派发、不计数、不续接，等它的结构化通知。
    ctx.ui.notify(`等子代理回报：${snap.pending_workers.join(",")}；不重复派发。`, "info");
    guardEvent("wait-worker", { workers: snap.pending_workers });
    return;
  }
  if (snap.done_met) {
    const identity = boundIdentity();
    const finished = identity ? finishRun(identity) : false;
    guardEvent("finish", { ok: finished });
    ctx.ui.notify(finished ? `run ${bound.runId} 判据已满足，已生成收据。` : `run ${bound.runId} 判据已满足，但收据生成失败，请看 handoff。`, finished ? "info" : "warning");
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
    if (decision.handoff) return stopWithHandoff(ctx, inherited, decision.reason);
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
    guardEvent("boundary", { choice, nonce: mark.nonce });
    memory.boundaryNonce = mark.nonce;
  }
  // 计数只经 xr 落盘；写失败就停，避免内存与磁盘分叉后无限续跑。
  const identity = boundIdentity();
  if (!identity || !saveGuardMemory(identity, { continues: memory.continues + 1, stalled, fingerprint, boundaryNonce: memory.boundaryNonce })) {
    return stopWithHandoff(ctx, inherited, "续跑计数写不进去（xr guard set 失败）");
  }
  guardEvent("resume", {});
  const entries: SessionBoundaryDraft[] = [...inherited];
  if (choice === "compact") {
    const capsule = readCapsule(bound.dir) || `run ${bound.runId}：胶囊缺失，先执行 xr capsule。`;
    entries.push({ type: "compaction", summary: compactText(capsule, null), firstKeptEntryId: null });
  }
  entries.push({ type: "custom_message", customType: "x-run-guard", content: continueMessage(snap, decision.message), display: true });
  return { continue: true, entries };
}

/** 续接只注入一次：带 run 目录和当前第一步，不让人再去问下一步做什么。 */
function continueMessage(snap: InspectSnapshot, base: string): string {
  const next = snap.doing[0] ?? snap.ready[0];
  const dir = bound?.dir ?? "";
  return [
    base,
    `运行目录：${dir}`,
    next ? `下一步：xr next（当前 ${next}）` : "下一步：xr next",
    `不要重做已有 VERIFIED 单元；没有可做项就走 review 或 land。`,
  ].join("\n");
}

/** 判据满足时由守卫收口；失败只记录，不假装完成。 */
function finishRun(identity: HostIdentity): boolean {
  const bin = xrPath(identity.workspace);
  if (!bin) return false;
  try {
    execFileSync(bin, ["--repo", identity.workspace, "--run-id", identity.runId,
      "--session", identity.sessionId, "--generation", String(identity.generation), "finish"],
      { stdio: "ignore", timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

/** handoff 写不下去也要停：宁可暂停，不带着失效状态继续跑。 */
function stopWithHandoff(
  ctx: ExtensionContext,
  inherited: SessionBoundaryDraft[],
  why: string,
): { continue: false; entries: SessionBoundaryDraft[] } {
  const runId = bound?.runId ?? "unknown";
  try {
    if (!bound) throw new Error("未绑定运行");
    writeAtomic(path.join(bound.dir, "handoff.md"), renderHandoff(runId, why));
    guardEvent("handoff", { reason: why });
    ctx.ui.notify(`停止自动续跑：${why}`, "warning");
  } catch (error) {
    guardEvent("handoff-failed", { reason: why, error: error instanceof Error ? error.message : String(error) });
    ctx.ui.notify(`停止自动续跑：${why}；写 handoff.md 失败（${error instanceof Error ? error.message : String(error)}），已停在原状态。`, "error");
  }
  return { continue: false, entries: inherited };
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
