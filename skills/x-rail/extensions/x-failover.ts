import type { AgentBeforeSettleEvent, ExtensionAPI, ExtensionContext, SessionBoundaryDraft } from "@earendil-works/pi-coding-agent";
import { PRIMARY, modelKey } from "./constants.ts";
import { classifyError, assistantErrorText } from "./classify.ts";
import { noteFailback, noteProbe, observe } from "./breaker.ts";
import { decideFailback } from "./failback.ts";
import { planSwitch } from "./compat.ts";
import { decideSwitch, freshMemory, memoryAfter } from "./switch.ts";
import { breakerFor, loadState, memoryFor, statePath, updateState, type Persisted } from "./store.ts";
import { appendEvent, findActiveRun, readBoundary } from "./run-files.ts";
import { registerGuardLifecycle } from "./x-run-guard.ts";

let sessionMemory = freshMemory();

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
  registerGuardLifecycle(pi, async (ctx) => {
    const target = ctx.modelRegistry.find("bai", "deepseek-v4.1-flash");
    if (!target || !(await pi.setModel(target))) {
      ctx.ui.notify("看门狗判定模型无响应，但找不到可用兜底模型；已停止自动续跑。", "error");
      return;
    }
    pi.setThinkingLevel("high");
    pi.sendMessage(
      { customType: "x-failover", content: "[x-failover] 看门狗检测到模型无响应，已切换兜底模型。继续当前工作。", display: true },
      { triggerTurn: true },
    );
  });
  pi.registerCommand("x-failover", {
    description: "查看或开关模型降级",
    handler: async (args, ctx) => {
      const file = statePath();
      const state = loadState(file);
      const cmd = args.trim();
      if (cmd === "off") {
        updateState(file, (latest) => { latest.disabled = true; });
        ctx.ui.notify("x-failover 已关闭。熔断记录还在。", "warning");
        return;
      }
      if (cmd === "on") {
        updateState(file, (latest) => { latest.disabled = false; });
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

  pi.on("session_start", async () => {
    sessionMemory = freshMemory();
  });
  pi.on("tool_result", async (_event, ctx) => {
    const located = findActiveRun(ctx.cwd);
    if (!located) return;
    const file = statePath();
    updateState(file, (state) => {
      const memory = memoryFor(state, located.id);
      state.runs[located.id] = { ...memory, toolCallsSinceFailover: memory.toolCallsSinceFailover + 1 };
    });
  });

  pi.on("agent_before_settle", async (event: AgentBeforeSettleEvent, ctx: ExtensionContext) => {
    const file = statePath();
    const state = loadState(file);
    const located = findActiveRun(ctx.cwd);
    const memory = located ? memoryFor(state, located.id) : sessionMemory;
    const current = currentModel(ctx);
    let needsCompaction = false;
    if (event.outcome === "completed" && located && ctx.model?.provider === "bai") {
      const mark = readBoundary(located.dir);
      if (mark && mark.nonce !== state.boundaryNonce) {
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
        needsCompaction = back.action === "compact-then-switch-back";
        updateState(file, (latest) => { latest.boundaryNonce = mark.nonce; });
        if (back.action !== "stay") {
          const primary = ctx.modelRegistry.find(PRIMARY.provider, PRIMARY.id);
          if (primary) {
            const switched = await pi.setModel(primary);
            if (switched) {
              updateState(file, (latest) => {
                const key = modelKey(PRIMARY.provider, PRIMARY.id);
                latest.breakers[key] = noteFailback(breakerFor(latest, key), Date.now());
              });
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
      watchdog: false,
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
    updateState(file, (latest) => {
      if (!latest.disabled && (classified.klass === "E1" || classified.klass === "E3" || classified.klass === "E5" || classified.klass === "E2")) {
        const key = modelKey(current.provider, current.id);
        latest.breakers[key] = observe(breakerFor(latest, key), classified.klass, Date.now()).state;
      }
      if (located) {
        latest.runs[located.id] = memoryAfter(memoryFor(latest, located.id), decision);
      } else {
        sessionMemory = memoryAfter(sessionMemory, decision);
      }
    });
    if (planned.action === "ignore") {
      // 任务续跑只由守卫负责；这里仅在需要压缩时追加自己的条目，不覆盖守卫已写入的 entries。
      if (!needsCompaction) return;
      return { continue: true, entries: [...(event.entries ?? []), { type: "compaction", summary: "切回主模型。恢复状态以 capsule.md 和 ledger.tsv 为准。", firstKeptEntryId: null }] };
    }
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
        entries: [...(event.entries ?? []), { type: "custom_message" as const, customType: "x-failover", content: `[x-failover] ${planned.reason}`, display: true }],
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
    const content = "message" in planned ? planned.message : "";
    const entries: SessionBoundaryDraft[] = [...(event.entries ?? [])];
    if (planned.action === "compact-then-switch") {
      entries.push({ type: "compaction", summary: "跨模型切换。恢复状态以 capsule.md 和 ledger.tsv 为准。", firstKeptEntryId: null });
    }
    entries.push({ type: "custom_message", customType: "x-failover", content, display: true });
    return { continue: true, entries };
  });

}

export function applyProbe(ok: boolean): void {
  const file = statePath();
  updateState(file, (state) => {
    const key = modelKey(PRIMARY.provider, PRIMARY.id);
    state.breakers[key] = noteProbe(breakerFor(state, key), ok);
  });
}
