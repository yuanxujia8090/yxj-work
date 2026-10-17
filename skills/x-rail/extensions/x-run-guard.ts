import fs from "node:fs";
import path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { SUMMARY_MODEL, SUMMARY_TIMEOUT_MS } from "./constants.ts";
import {
  boundaryDecision,
  compactText,
  nextStall,
  renderHandoff,
  resumeHint,
  shouldContinue,
  watchdogDue,
} from "./guard-core.ts";
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
import { markWatchdog } from "./watchdog.ts";

let lastTokenAt = Date.now();
let userAbort = false;
let watchdogTimer: ReturnType<typeof setTimeout> | undefined;

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    const hint = resumeHint(located?.id ?? null);
    if (hint) ctx.ui.notify(hint, "info");
  });

  pi.on("message_update", async () => {
    lastTokenAt = Date.now();
  });

  pi.on("provider_stream_event", async () => {
    lastTokenAt = Date.now();
  });

  pi.on("agent_start", async (_event, ctx) => {
    userAbort = false;
    lastTokenAt = Date.now();
    if (watchdogTimer) clearTimeout(watchdogTimer);
    const arm = () => {
      watchdogTimer = setTimeout(() => {
        if (watchdogDue(lastTokenAt, Date.now(), userAbort)) {
          markWatchdog();
          ctx.abort();
          return;
        }
        arm();
      }, 5_000);
    };
    arm();
  });

  pi.on("agent_settled", async (event) => {
    if (watchdogTimer) clearTimeout(watchdogTimer);
    if (event.aborted) userAbort = true;
  });

  pi.on("agent_before_settle", async (event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    if (!located) return;
    const snap = runSnapshot(located.dir, located.id);
    const memory = loadGuardMemory(located.dir);
    const fingerprint = unitsFingerprint(located.dir);
    const stalled = memory.continues === 0 ? 0 : nextStall(memory.fingerprint, fingerprint, memory.stalled);
    const decision = shouldContinue({
      outcome: event.outcome,
      run: {
        id: located.id,
        active: true,
        doneMet: snap.doneMet,
        allBlockedByGate: snap.allBlockedByGate,
        fingerprint,
        continues: memory.continues,
        stalledFingerprints: stalled,
      },
    });
    if (decision.action === "ignore") return;
    if (decision.action === "stop") {
      if (decision.handoff) {
        fs.writeFileSync(path.join(located.dir, "handoff.md"), renderHandoff(located.id, decision.reason));
        appendEvent(located.dir, { type: "handoff", reason: decision.reason, ts: new Date().toISOString() });
      }
      ctx.ui.notify(decision.reason, "warning");
      return;
    }
    refreshCapsule(ctx.cwd);
    const mark = readBoundary(located.dir);
    if (mark && mark.nonce !== memory.boundaryNonce) {
      const usage = ctx.getContextUsage();
      const choice = boundaryDecision({
        contextTokens: usage?.tokens ?? null,
        provider: ctx.model?.provider ?? "openai26",
        nextDependsOnReasoning: mark.dependsOnReasoning,
        nextUnrelated: mark.unrelated,
        nextCanBeUnattended: mark.unattended,
      });
      appendEvent(located.dir, { type: "boundary", choice, ts: new Date().toISOString(), nonce: mark.nonce });
      const resolved = choice === "new-session" ? "compact" : choice;
      if (resolved === "compact") ctx.compact({ customInstructions: "单元边界。摘要以胶囊为准。" });
      memory.boundaryNonce = mark.nonce;
    }
    saveGuardMemory(located.dir, {
      continues: memory.continues + 1,
      stalled,
      fingerprint,
      boundaryNonce: memory.boundaryNonce,
    });
    appendEvent(located.dir, { type: "resume", ts: new Date().toISOString() });
    return {
      continue: true,
      entries: [{ type: "custom_message" as const, customType: "x-run-guard", content: decision.message, display: true }],
    };
  });

  pi.on("session_before_compact", async (event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    if (!located) return;
    refreshCapsule(ctx.cwd);
    const capsule = readCapsule(located.dir) || `run ${located.id}：胶囊缺失，先执行 xr capsule。`;
    const supplement = await summarize(ctx, event.signal);
    appendEvent(located.dir, { type: "compaction", supplement: Boolean(supplement), ts: new Date().toISOString() });
    return {
      compaction: {
        summary: compactText(capsule, supplement),
        firstKeptEntryId: event.preparation.firstKeptEntryId,
        tokensBefore: event.preparation.tokensBefore,
      },
    };
  });
}

async function summarize(ctx: ExtensionContext, parent: AbortSignal): Promise<string | null> {
  if (process.env.X_RUN_GUARD_SUMMARY === "0") return null;
  const model = ctx.modelRegistry.find(SUMMARY_MODEL.provider, SUMMARY_MODEL.id);
  if (!model) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SUMMARY_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  parent.addEventListener("abort", onAbort);
  try {
    const response = await ctx.modelRegistry.complete(
      model,
      { messages: [] },
      { maxTokens: 800, thinkingLevel: "low", signal: controller.signal },
    );
    const text = response.content
      .filter((item): item is { type: "text"; text: string } => item.type === "text" && "text" in item)
      .map((item) => item.text)
      .join("\n");
    return text.trim() || null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
    parent.removeEventListener("abort", onAbort);
  }
}
