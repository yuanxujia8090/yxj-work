/**
 * Pi 模型恢复插件入口。
 *
 * 独立产物：只注册一个可选虚拟模型 `model-recovery/auto`，不改默认模型、不写用户配置、
 * 不发健康探测请求。任务状态与完成判断不在本插件内。
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
  CHAIN_EXHAUSTED,
  MISSING_FAILED,
  decideRequest,
  isContextRecoveryStop,
  keyOf,
  markGatewayError,
  parseConfig,
  parseState,
  type BranchState,
  type RecoveryConfig,
} from "./decide.ts";

function failedTextOf(message: unknown): string {
  // 只认错误字段：assistant 正常回答里出现“余额/401”不代表请求失败原因。
  const item = message as { errorMessage?: unknown } | undefined;
  return typeof item?.errorMessage === "string" ? item.errorMessage : "";
}

export const PROVIDER = "model-recovery";
export const MODEL_ID = "auto";
export const MODEL_NAME = "Model Recovery (auto)";

export interface LoadedConfig {
  path: string;
  config: RecoveryConfig | null;
  error: string | null;
}

/** 配置路径只认宿主环境变量或宿主默认目录，不写死个人路径。 */
export function configPath(env: NodeJS.ProcessEnv = process.env, home: string = os.homedir()): string {
  const explicit = env.PI_MODEL_RECOVERY_CONFIG;
  if (explicit) return path.resolve(explicit);
  const agentDir = env.PI_CODING_AGENT_DIR || path.join(home, ".pi", "agent");
  return path.join(agentDir, "model-recovery.json");
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env, home: string = os.homedir()): LoadedConfig {
  const file = configPath(env, home);
  let raw: string;
  try {
    raw = fs.readFileSync(file, "utf8");
  } catch {
    return { path: file, config: null, error: "未配置（找不到配置文件）" };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { path: file, config: null, error: "配置不是合法 JSON" };
  }
  const result = parseConfig(parsed);
  if (!result.ok) return { path: file, config: null, error: result.error };
  return { path: file, config: result.config, error: null };
}

function hostRetrySettings(env: NodeJS.ProcessEnv = process.env, home: string = os.homedir()): string {
  const agentDir = env.PI_CODING_AGENT_DIR || path.join(home, ".pi", "agent");
  try {
    const settings = JSON.parse(fs.readFileSync(path.join(agentDir, "settings.json"), "utf8")) as {
      retry?: { enabled?: boolean; maxRetries?: number; baseDelayMs?: number };
    };
    const retry = settings.retry;
    if (!retry) return "宿主 retry 未配置（Pi 默认值生效）";
    return `宿主 retry: enabled=${retry.enabled ?? "default"} maxRetries=${retry.maxRetries ?? "default"} baseDelayMs=${retry.baseDelayMs ?? "default"}`;
  } catch {
    return "宿主 retry 设置不可读（不影响本插件；插件不修改它）";
  }
}

export function statusText(loaded: LoadedConfig, selection: string): string {
  const lines = [`配置路径：${loaded.path}`];
  if (!loaded.config) {
    lines.push(`状态：${loaded.error ?? "未配置"}`);
    lines.push("虚拟模型：未注册（普通物理模型不受影响）");
    return lines.join("\n");
  }
  lines.push(`有效链：${loaded.config.chain.map(keyOf).join(" → ")}`);
  lines.push(`冷却配置：${loaded.config.cooldownMs} ms（实际分支冷却由宿主保存，status 不读取）`);
  lines.push(`网关兼容：${loaded.config.gatewayCompatibility ? "开" : "关"}`);
  lines.push(`当前选择：${selection}`);
  lines.push(hostRetrySettings());
  const suggested = Math.max(0, loaded.config.chain.length - 1);
  lines.push(`建议（需你自行应用，本插件不改）：maxRetries=${suggested} baseDelayMs=1000`);
  return lines.join("\n");
}

export default function modelRecovery(pi: ExtensionAPI): void {
  const loaded = loadConfig();
  const active: RecoveryConfig | null = loaded.config;

  pi.registerCommand("model-recovery", {
    description: "只读显示模型恢复插件的配置与宿主重试设置",
    handler: async (args: string, ctx: ExtensionContext) => {
      const selection = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "未知";
      const text = statusText(loaded, selection);
      ctx.ui.notify(args.trim() && args.trim() !== "status" ? `用法：/model-recovery status\n${text}` : text,
        args.trim() && args.trim() !== "status" ? "warning" : "info");
    },
  });

  if (!loaded.config) {
    // 配置缺失或无效：不注册虚拟模型，不替代任何模型，错误由 /model-recovery status 显示。
    return;
  }

  pi.registerVirtualModel<BranchState>({
    provider: PROVIDER,
    id: MODEL_ID,
    name: MODEL_NAME,
    thinkingLevels: ["off", "low", "medium", "high"],
    route(request, ctx) {
      const config = active;
      if (!config) throw new Error("model-recovery: 配置不可用");
      const failed = request.failed
        ? { provider: request.failed.model.provider, model: request.failed.model.id }
        : null;
      // 上下文/截断：沿用失败模型，不消耗故障链（stopReason 枚举见 Pi 的 StopReason）。
      const contextRecovery = request.reason === "retry" && isContextRecoveryStop(request.failed?.message);
      const decision = decideRequest({
        reason: request.reason,
        config,
        // 只信宿主分支状态；没有就是空状态，不用模块级变量跨会话共享。
        state: parseState(request.state),
        now: Date.now(),
        failed,
        failedText: failedTextOf(request.failed?.message),
        contextRecovery,
      });
      if (decision.action === "fail") {
        // 终止错误文本已避开暂时故障词，避免宿主再次当可重试错误。
        throw new Error(decision.error);
      }
      const entry = config.chain[decision.index];
      const model = ctx.modelRegistry.find(entry.provider, entry.model);
      if (!model) {
        throw new Error(`model-recovery: 配置的模型不可用或无凭据：${keyOf(entry)}`);
      }
      return {
        model,
        thinkingLevel: request.thinkingLevel,
        state: decision.state,
      };
    },
  });

  // 只处理真正失败的 assistant 消息；不改未知/鉴权/余额文案。
  pi.on("message_end", async (event, ctx) => {
    const config = active;
    if (!config?.gatewayCompatibility) return;
    // 只处理选中本虚拟模型的会话；普通物理模型会话一律不改写。
    if (ctx.model?.provider !== PROVIDER || ctx.model.id !== MODEL_ID) return;
    const message = event.message as { role?: string; stopReason?: string; errorMessage?: string } | undefined;
    if (!message || message.role !== "assistant" || !message.stopReason || message.stopReason === "stop") return;
    const text = message.errorMessage ?? "";
    if (!text) return;
    const decision = markGatewayError(text, true);
    if (decision.action !== "mark") return;
    // 只替换 errorMessage，角色和其余字段不动。
    return { message: { ...event.message, errorMessage: decision.text } as typeof event.message };
  });

  // 供测试读取，不参与路由。
  pi.on("session_start", async (_event, ctx) => {
    if (ctx.model?.provider === PROVIDER && ctx.model.id === MODEL_ID) {
      const chain = active ? active.chain.map(keyOf).join(" → ") : "配置不可用";
      ctx.ui.notify(`已选择 ${PROVIDER}/${MODEL_ID}：${chain}`, "info");
    }
  });
}

/** 供探针直接检查配置解析结果，不触发请求。 */
export function describeForProbe(env: NodeJS.ProcessEnv = process.env, home: string = os.homedir()): LoadedConfig {
  return loadConfig(env, home);
}
