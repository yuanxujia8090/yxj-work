import fs from "node:fs";

export default function (pi: any) {
  const record = (event: any, ctx?: any) => fs.appendFileSync(process.env.HOST_PROBE_EVENTS!, `${JSON.stringify({
    at: Date.now(), pid: process.pid, sessionId: ctx?.sessionManager.getSessionId(),
    sessionFile: ctx?.sessionManager.getSessionFile(), ...event,
  })}\n`);
  record({ type: "extension_loaded" });
  for (const type of ["session_start", "session_shutdown", "agent_start", "agent_end", "agent_before_settle", "agent_settled", "turn_start", "turn_end", "message_end", "tool_execution_start", "tool_execution_end", "tool_result"]) {
    pi.on(type, (event: any, ctx: any) => {
      record(event, ctx);
      if (type === "message_end" && event.message?.role === "assistant" && event.message.stopReason === "error" && event.message.errorMessage === "gateway_concurrency_limit") {
        return { ...event.message, errorMessage: `${event.message.errorMessage} [host-probe retryable]` };
      }
    });
  }
  pi.on("tool_call", (event: any, ctx: any) => {
    record(event, ctx);
    if (event.toolName === "probe_action" && event.input.mode === "blocked") {
      record({ type: "block_decision", toolCallId: event.toolCallId }, ctx);
      return { block: true, reason: "host-probe intentional block" };
    }
  });
  pi.registerVirtualModel({
    provider: "host-probe",
    id: "auto",
    name: "Host probe auto",
    thinkingLevels: ["off"],
    route(request: any, ctx: any) {
      const selected = request.reason === "retry" ? "fixture-b" : request.previous?.model?.id ?? "fixture-a";
      const model = ctx.modelRegistry.find("host-probe", selected);
      if (!model) throw new Error(`host-probe missing physical model: ${selected}`);
      record({ type: "route", reason: request.reason, selected, failed: request.failed?.message?.errorMessage }, ctx);
      return { model, thinkingLevel: "off" };
    },
  });
  pi.on("before_provider_request", (_event: any, ctx: any) => {
    if (ctx.model?.provider !== "host-probe" || !ctx.model.baseUrl.startsWith(`http://127.0.0.1:${process.env.HOST_PROBE_PORT}/`)) {
      throw new Error("host-probe requires loopback model");
    }
    record({ type: "provider_target", provider: ctx.model.provider, model: ctx.model.id, baseUrl: ctx.model.baseUrl }, ctx);
  });
  pi.registerTool({
    name: "probe_action", label: "Probe action", description: "Local lifecycle fixture", executionMode: "sequential",
    parameters: { type: "object", properties: { mode: { type: "string", enum: ["ok", "fail", "blocked", "child"] } }, required: ["mode"], additionalProperties: false },
    async execute(toolCallId: string, input: { mode: string }, _signal: unknown, _update: unknown, ctx: any) {
      record({ type: "execute_enter", toolCallId, mode: input.mode, activeTools: pi.getActiveTools() }, ctx);
      if (input.mode === "fail") throw new Error("host-probe intentional failure");
      return { content: [{ type: "text", text: `host-probe ${input.mode} executed` }], details: { mode: input.mode } };
    },
  });
}
