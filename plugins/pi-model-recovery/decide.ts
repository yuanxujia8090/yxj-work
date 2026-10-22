/** 模型恢复插件的纯决策层：不导入宿主、不读环境、不发请求。 */

export interface ChainEntry {
  provider: string;
  model: string;
}

export interface RecoveryConfig {
  schema: 1;
  chain: ChainEntry[];
  cooldownMs: number;
  gatewayCompatibility: boolean;
}

export interface BranchState {
  schema: 1;
  activeIndex: number;
  cooldownUntil: number | null;
  attempted: string[];
}

export type ParseResult =
  | { ok: true; config: RecoveryConfig }
  | { ok: false; error: string };

export function keyOf(entry: ChainEntry): string {
  return `${entry.provider}/${entry.model}`;
}

export function emptyState(): BranchState {
  return { schema: 1, activeIndex: 0, cooldownUntil: null, attempted: [] };
}

/** 配置只读校验：缺失/结构错/链过长都明确报错，不悄悄挑替代模型。 */
export function parseConfig(raw: unknown): ParseResult {
  if (raw === null || typeof raw !== "object") return { ok: false, error: "配置缺失或不是 JSON 对象" };
  const item = raw as Record<string, unknown>;
  if (item.schema !== 1) return { ok: false, error: "配置 schema 必须是 1" };
  if (!Array.isArray(item.chain)) return { ok: false, error: "配置 chain 必须是数组" };
  if (item.chain.length === 0) return { ok: false, error: "配置 chain 为空" };
  if (item.chain.length > 3) return { ok: false, error: "配置 chain 最多 3 个模型" };
  const chain: ChainEntry[] = [];
  const seen = new Set<string>();
  for (const entry of item.chain) {
    if (!entry || typeof entry !== "object") return { ok: false, error: "chain 条目必须是对象" };
    const { provider, model } = entry as Record<string, unknown>;
    if (typeof provider !== "string" || !provider.trim()) return { ok: false, error: "chain 条目缺少 provider" };
    if (typeof model !== "string" || !model.trim()) return { ok: false, error: "chain 条目缺少 model" };
    const key = `${provider}/${model}`;
    if (seen.has(key)) continue;
    seen.add(key);
    chain.push({ provider, model });
  }
  if (chain.length === 0) return { ok: false, error: "配置 chain 去重后为空" };
  const cooldownMs = item.cooldownMs ?? 600_000;
  if (typeof cooldownMs !== "number" || !Number.isFinite(cooldownMs) || cooldownMs < 0) {
    return { ok: false, error: "cooldownMs 必须是非负数字" };
  }
  const gatewayCompatibility = item.gatewayCompatibility ?? true;
  if (typeof gatewayCompatibility !== "boolean") return { ok: false, error: "gatewayCompatibility 必须是布尔值" };
  return { ok: true, config: { schema: 1, chain, cooldownMs, gatewayCompatibility } };
}

/** 宿主分支状态可能是旧结构或坏值；解析不了就从空状态开始，不猜索引。 */
export function parseState(raw: unknown): BranchState {
  if (!raw || typeof raw !== "object") return emptyState();
  const item = raw as Record<string, unknown>;
  if (item.schema !== 1) return emptyState();
  const activeIndex = typeof item.activeIndex === "number" && Number.isInteger(item.activeIndex) && item.activeIndex >= 0
    ? item.activeIndex : 0;
  const cooldownUntil = typeof item.cooldownUntil === "number" && Number.isFinite(item.cooldownUntil) ? item.cooldownUntil : null;
  const attempted = Array.isArray(item.attempted) ? item.attempted.filter((value): value is string => typeof value === "string") : [];
  return { schema: 1, activeIndex, cooldownUntil, attempted };
}

export type RequestReason = "user" | "continuation" | "retry" | "direct";

/**
 * 判断一次失败是否属于“上下文/截断”，这类重试沿用失败模型，不消耗故障链。
 * 依据 Pi 的 StopReason：length（截断）与带上下文关键词的 error；
 * 不是宿主内部的 isContextOverflow 全量实现，宁可少判也不把服务故障当溢出。
 */
export function isContextRecoveryStop(message: unknown): boolean {
  const item = message as { stopReason?: unknown; errorMessage?: unknown } | undefined;
  if (!item) return false;
  if (item.stopReason === "length") return true;
  if (item.stopReason === "error" && typeof item.errorMessage === "string") {
    return /context[ _-]?(length|window|limit)|prompt is too long|maximum context|too many tokens|token limit|exceed[s]? (the )?(maximum|context)/i.test(item.errorMessage);
  }
  return false;
}

export interface DecideInput {
  reason: RequestReason;
  config: RecoveryConfig;
  state: BranchState;
  now: number;
  failed?: { provider?: string; model?: string } | null;
  failedText?: string;
  contextRecovery?: boolean;
}

export type DecideResult =
  | { action: "use"; index: number; state?: BranchState }
  | { action: "fail"; error: string; state?: BranchState };

export const CHAIN_EXHAUSTED = "model-recovery: 配置链已用尽，不再发起物理请求";
export const MISSING_FAILED = "model-recovery: 缺少失败模型信息，无法安全换链";
export const NOT_RETRYABLE = "model-recovery: 该错误不由插件换链处理";

function clampIndex(index: number, length: number): number {
  return index >= 0 && index < length ? index : 0;
}

/** 结束一轮时清空尝试记录；冷却只在用户新输入时过期。 */
function resetForUser(state: BranchState, config: RecoveryConfig, now: number): BranchState {
  const cooled = state.cooldownUntil !== null && state.cooldownUntil <= now;
  return {
    schema: 1,
    activeIndex: cooled ? 0 : clampIndex(state.activeIndex, config.chain.length),
    cooldownUntil: cooled ? null : state.cooldownUntil,
    attempted: [],
  };
}

export function decideRequest(input: DecideInput): DecideResult {
  const { reason, config, now } = input;
  const state = parseState(input.state);
  if (config.chain.length === 0) return { action: "fail", error: "model-recovery: 配置链为空" };
  if (reason === "user") {
    const next = resetForUser(state, config, now);
    return { action: "use", index: clampIndex(next.activeIndex, config.chain.length), state: next };
  }
  if (reason === "continuation") {
    // 沿用最近成功模型，保持缓存与上下文；没有 previous 就用当前索引。
    return { action: "use", index: clampIndex(state.activeIndex, config.chain.length) };
  }
  if (reason === "direct") {
    return { action: "use", index: clampIndex(state.activeIndex, config.chain.length) };
  }
  // retry
  if (input.contextRecovery) {
    // 上下文溢出沿用失败模型，不消耗故障链。
    const index = input.failed ? config.chain.findIndex((entry) => keyOf(entry) === keyOf(input.failed as ChainEntry)) : -1;
    return { action: "use", index: index >= 0 ? index : clampIndex(state.activeIndex, config.chain.length) };
  }
  if (!input.failed || (!input.failed.provider && !input.failed.model)) {
    return { action: "fail", error: MISSING_FAILED };
  }
  // 鉴权、余额、权限类不换链：换模型只会绕过费用或凭据问题。
  if (input.failedText && NON_TRANSIENT.some((token) => input.failedText!.includes(token))) {
    return { action: "fail", error: NOT_RETRYABLE };
  }
  const failedKey = `${input.failed.provider ?? ""}/${input.failed.model ?? ""}`;
  const failedIndex = config.chain.findIndex((entry) => keyOf(entry) === failedKey);
  const attempted = new Set(state.attempted);
  attempted.add(failedKey);
  const start = failedIndex >= 0 ? failedIndex + 1 : 0;
  for (let offset = 0; offset < config.chain.length; offset += 1) {
    const index = (start + offset) % config.chain.length;
    const key = keyOf(config.chain[index]);
    if (attempted.has(key)) continue;
    const next: BranchState = {
      schema: 1,
      activeIndex: index,
      cooldownUntil: now + config.cooldownMs,
      attempted: [...attempted, key],
    };
    return { action: "use", index, state: next };
  }
  const exhausted: BranchState = { schema: 1, activeIndex: clampIndex(state.activeIndex, config.chain.length), cooldownUntil: state.cooldownUntil, attempted: [...attempted] };
  return { action: "fail", error: CHAIN_EXHAUSTED, state: exhausted };
}

const GATEWAY_PATTERNS = [
  "账号池暂无可用账号",
  "gateway_concurrency_limit",
  "The service is busy",
  "Upstream stream ended prematurely",
];

/** 明确不是暂时故障的文案；命中就不加标记，避免把费用/凭据问题当重试。 */
const NON_TRANSIENT = [
  "鉴权", "未授权", "余额", "额度", "欠费", "权限", "无权",
  "401", "402", "403", "insufficient_quota", "invalid_api_key", "permission_denied",
];

export const TRANSIENT_MARKER = "[model-recovery: temporary gateway error]";

export type MarkerDecision =
  | { action: "keep"; reason: string }
  | { action: "mark"; text: string; reason: string };

/** 只附加标记，不删除原文；已是标记过的不重复追加。 */
export function markGatewayError(text: string, enabled: boolean): MarkerDecision {
  if (!enabled) return { action: "keep", reason: "gatewayCompatibility 关闭" };
  const body = typeof text === "string" ? text : "";
  if (body.includes(TRANSIENT_MARKER)) return { action: "keep", reason: "已标记" };
  if (NON_TRANSIENT.some((token) => body.includes(token))) return { action: "keep", reason: "鉴权/余额/权限类，不改写" };
  const hit = GATEWAY_PATTERNS.find((pattern) => body.includes(pattern));
  if (!hit) return { action: "keep", reason: "未命中已知网关文案" };
  return { action: "mark", text: `${body}\n${TRANSIENT_MARKER}`, reason: `命中 ${hit}` };
}

/** 状态必须能直接 JSON 往返；返回字符串供宿主保存。 */
export function encodeState(state: BranchState): string {
  return JSON.stringify({ schema: 1, activeIndex: state.activeIndex, cooldownUntil: state.cooldownUntil, attempted: state.attempted });
}
