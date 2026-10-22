import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { recordHostEvent, receiveWorker, workerUnit, type HostIdentity } from "./run-files.ts";

/** 纯读取白名单；未列入的一律按“可能产生副作用”处理。 */
const READONLY_TOOLS = new Set(["read", "ls", "find", "grep", "glob"]);

/** 由任务守卫提供当前绑定；未绑定或代次缺失时返回 null。 */
export type IdentitySource = () => HostIdentity | null;

function summarize(args: unknown): Record<string, unknown> {
  // 原始参数可能含凭据，只留类型与少量结构信息。
  if (typeof args !== "object" || args === null) return { kind: typeof args };
  const keys = Object.keys(args as Record<string, unknown>).slice(0, 12);
  return { kind: "object", keys };
}

export function registerHostEvents(pi: ExtensionAPI, identityOf: IdentitySource): void {
  const identities = new Map<string, HostIdentity>();
  const launches = new Map<string, { identity: HostIdentity; unit: string; statusPath: string }>();
  const eventId = (identity: HostIdentity, callId: string, suffix: string) => createHash("sha256")
    .update(JSON.stringify([identity.runId, identity.sessionId, identity.generation, callId, suffix])).digest("hex");
  const writeIntent = (identity: HostIdentity, toolCallId: string, toolName: string, input: unknown, parent: string | null) => recordHostEvent(
    identity, eventId(identity, toolCallId, "intent"), "op_intent", {
      op_id: toolCallId,
      tool: toolName,
      readonly: READONLY_TOOLS.has(toolName),
      parent,
      args: summarize(input),
    },
  );
  pi.on("tool_execution_start", async (event, _ctx) => {
    const identity = identityOf();
    if (identity) identities.set(event.toolCallId, identity);
  });

  pi.on("tool_call", async (event, _ctx) => {
    const identity = identities.get(event.toolCallId) ?? identityOf();
    if (!identity) return;
    identities.set(event.toolCallId, identity);
    // 意图写入失败时宁可阻断执行，也不要留下没有记录的副作用。
    const written = writeIntent(identity, event.toolCallId, event.toolName, event.input, event.parentToolCallId ?? null);
    if (written === "rejected" || written === "unavailable") {
      return { block: true, reason: `x-rail 无法记录工具意图（${written}），已阻止可能产生副作用的执行。` };
    }
  });

  pi.on("tool_execution_end", async (event, _ctx) => {
    const identity = identities.get(event.toolCallId);
    identities.delete(event.toolCallId);
    if (!identity) return;
    const ran = event.durationMs !== undefined;
    if (!ran) {
      // 工具根本没有执行：不存在副作用，按未开始记录。
      recordHostEvent(identity, eventId(identity, event.toolCallId, "not-started"), "op_reconcile", {
        op_id: event.toolCallId,
        resolution: "not-started",
        record: "host:no-execution",
      });
      return;
    }
    // isError 只证明报错，不证明没写入；只有成功才自动关闭动作。
    recordHostEvent(identity, eventId(identity, event.toolCallId, "result"), "op_result", {
      op_id: event.toolCallId,
      outcome: event.isError ? "error" : "success",
      tool: event.toolName,
      duration_ms: event.durationMs ?? null,
    });
    if (event.isError) return;
    const result = event.result as { details?: Record<string, unknown> } | undefined;
    const details = result?.details;
    if (event.toolName === "subagent" && details && typeof details.runId === "string" && typeof details.asyncDir === "string") {
      const unit = workerUnit(identity);
      if (!unit) return;
      const statusPath = `${details.asyncDir}/status.json`;
      const launchDigest = typeof details.launchContractDigest === "string" ? details.launchContractDigest : "unknown";
      const launched = recordHostEvent(identity, eventId(identity, event.toolCallId, "started"), "worker_started", {
        op_id: event.toolCallId,
        unit,
        child_run_id: details.runId,
        status_path: statusPath,
        launch_digest: launchDigest,
        parent_session_id: identity.sessionId,
      });
      if (launched === "ok" || launched === "duplicate") launches.set(String(details.runId), { identity, unit, statusPath });
    }
  });

  pi.on("message_end", async (event, _ctx) => {
    const message = event.message as { role?: string; customType?: string; details?: { runs?: unknown } };
    if (message.role !== "custom" || message.customType !== "subagent-notify" || !Array.isArray(message.details?.runs)) return;
    for (const item of message.details.runs) {
      if (typeof item !== "object" || item === null || typeof item.runId !== "string") continue;
      const launch = launches.get(item.runId);
      if (launch) receiveWorker(launch.identity, launch.unit, launch.statusPath);
    }
  });
}
