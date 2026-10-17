import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { PRIMARY, modelKey } from "./constants.ts";
import { classifyError, assistantErrorText } from "./classify.ts";
import { noteFailback, noteProbe, observe } from "./breaker.ts";
import { decideFailback } from "./failback.ts";
import { planSwitch } from "./compat.ts";
import { decideSwitch, memoryAfter } from "./switch.ts";
import { breakerFor, loadState, memoryFor, saveState, statePath, type Persisted } from "./store.ts";
import { appendEvent, findActiveRun, readBoundary } from "./run-files.ts";
import { takeWatchdog } from "./watchdog.ts";

function currentModel(ctx: { model?: { provider: string; id: string } | undefined }): { provider: string; id: string } {
  if (ctx.model?.provider && ctx.model?.id) return { provider: ctx.model.provider, id: ctx.model.id };
  return { provider: PRIMARY.provider, id: PRIMARY.id };
}

function statusText(state: Persisted): string {
  const lines = [`x-failover ${state.disabled ? "off" : "on"}`];
  const keys = Object.keys(state.breakers);
  if (keys.length === 0) lines.push("熔断：无");
  for (const key of keys) {
    const item = state.breakers[key];
    lines.push(`${key} open=${item.open} cooldownMs=${item.cooldownMs} locked=${item.lockedToFallback}`);
  }
  return lines.join("\n");
}

export default function (pi: ExtensionAPI) {
  pi.registerCommand("x-failover", {
    description: "查看或开关模型降级",
    handler: async (args, ctx) => {
      const file = statePath();
      const state = loadState(file);
      const cmd = args.trim();
      if (cmd === "off") {
        state.disabled = true;
        saveState(file, state);
        ctx.ui.notify("x-failover 已关闭。熔断记录还在。", "warning");
        return;
      }
      if (cmd === "on") {
        state.disabled = false;
        saveState(file, state);
        ctx.ui.notify("x-failover 已打开。", "info");
        return;
      }
      if (cmd === "status" || cmd === "") {
        ctx.ui.notify(statusText(state), "info");
        return;
      }
      ctx.ui.notify("用法：/x-failover status|off|on", "warning");
    },
  });

  pi.on("tool_result", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    if (!located) return;
    const file = statePath();
    const state = loadState(file);
    const memory = memoryFor(state, located.id);
    memory.toolCallsSinceFailover += 1;
    state.runs[located.id] = memory;
    saveState(file, state);
  });

  pi.on("agent_before_settle", async (event, ctx) => {
    const file = statePath();
    const state = loadState(file);
    const located = findActiveRun(ctx.cwd);
    const runId = located?.id ?? "session";
    const memory = memoryFor(state, runId);
    const current = currentModel(ctx);
    if (event.outcome === "completed" && located && ctx.model?.provider === "bai") {
      const mark = readBoundary(located.dir);
      if (mark && mark.nonce !== state.boundaryNonce) {
        state.boundaryNonce = mark.nonce;
        const usage = ctx.getContextUsage();
        const back = decideFailback({
          now: Date.now(),
          breaker: breakerFor(state, modelKey(PRIMARY.provider, PRIMARY.id)),
          policy: "auto",
          onFallback: true,
          unitBoundary: true,
          newUserTurn: false,
          contextTokens: usage?.tokens ?? null,
          probeAvailable: process.env.X_FAILOVER_PROBE === "1",
        });
        saveState(file, state);
        if (back.action !== "stay") {
          if (back.action === "compact-then-switch-back") ctx.compact({ customInstructions: "切回前只保留胶囊。" });
          const primary = ctx.modelRegistry.find(PRIMARY.provider, PRIMARY.id);
          if (primary) {
            const switched = await pi.setModel(primary);
            if (switched) {
              const key = modelKey(PRIMARY.provider, PRIMARY.id);
              state.breakers[key] = noteFailback(breakerFor(state, key), Date.now());
              saveState(file, state);
              appendEvent(located.dir, { type: "failback", ts: new Date().toISOString(), reason: back.reason });
              pi.appendEntry("x-failover", { action: "failback", reason: back.reason });
            }
          }
        }
      }
    }
    const messages = event.context?.contextMessages ?? [];
    let last: unknown;
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const candidate = messages[i] as { role?: string };
      if (candidate?.role === "assistant") {
        last = messages[i];
        break;
      }
    }
    const extracted = assistantErrorText(last);
    const classified = classifyError({
      stopReason: event.outcome === "aborted" ? "aborted" : extracted.stopReason,
      text: extracted.text,
      watchdog: takeWatchdog(),
    });
    if (!state.disabled && (classified.klass === "E1" || classified.klass === "E3" || classified.klass === "E5" || classified.klass === "E2")) {
      const key = modelKey(current.provider, current.id);
      const observed = observe(breakerFor(state, key), classified.klass, Date.now());
      state.breakers[key] = observed.state;
    }
    const decision = decideSwitch({
      classified,
      current,
      memory,
      disabled: state.disabled,
      errorText: extracted.text,
    });
    const planned = planSwitch(decision, process.env.X_FAILOVER_REPLAY_COMPATIBLE !== "0");
    state.runs[runId] = memoryAfter(memory, decision);
    saveState(file, state);
    if (planned.action === "ignore") return;
    const record = { class: classified.klass, action: planned.action, from: modelKey(current.provider, current.id), ts: new Date().toISOString() };
    pi.appendEntry("x-failover", record);
    if (located) appendEvent(located.dir, { type: planned.action, ...record });
    if (planned.action === "handoff") {
      ctx.ui.notify(`x-failover 停止：${decision.action === "handoff" ? decision.reason : planned.action}`, "error");
      return;
    }
    if (planned.action === "retry-same") {
      if (planned.waitMs > 0 && process.env.X_FAILOVER_SKIP_WAIT !== "1") {
        await new Promise((resolve) => setTimeout(resolve, planned.waitMs));
      }
      return {
        continue: true,
        entries: [{ type: "custom_message" as const, customType: "x-failover", content: `[x-failover] ${planned.reason}`, display: true }],
      };
    }
    const target = ctx.modelRegistry.find("bai", "deepseek-v4.1-flash");
    if (!target) {
      pi.appendEntry("x-failover", { error: "no auth", model: "bai/deepseek-v4.1-flash" });
      ctx.ui.notify("找不到 bai/deepseek-v4.1-flash，或未配置认证。不循环切换。", "error");
      return;
    }
    const ok = await pi.setModel(target);
    if (!ok) {
      pi.appendEntry("x-failover", { error: "no auth" });
      ctx.ui.notify("bai 没有认证。不循环切换。", "error");
      return;
    }
    pi.setThinkingLevel("high");
    if (planned.action === "compact-then-switch") ctx.compact({ customInstructions: "只保留胶囊里的状态指针。" });
    const content = "message" in planned ? planned.message : "";
    return {
      continue: true,
      entries: [{ type: "custom_message" as const, customType: "x-failover", content, display: true }],
    };
  });

}

export function applyProbe(ok: boolean): void {
  const file = statePath();
  const state = loadState(file);
  const key = modelKey(PRIMARY.provider, PRIMARY.id);
  state.breakers[key] = noteProbe(breakerFor(state, key), ok);
  saveState(file, state);
}
