import {
  E2_RETRY_WAIT_MS,
  FALLBACK,
  MAX_FAILOVERS_PER_RUN,
  MAX_FAILOVERS_WITHOUT_PROGRESS,
  PRIMARY,
  modelKey,
} from "./constants.ts";
import type { ClassifiedError } from "./classify.ts";

export interface ModelRef {
  provider: string;
  id: string;
}

export interface RunMemory {
  failovers: number;
  sameModelRetries: number;
  failoversWithoutProgress: number;
  toolCallsSinceFailover: number;
}

export function freshMemory(): RunMemory {
  return { failovers: 0, sameModelRetries: 0, failoversWithoutProgress: 0, toolCallsSinceFailover: 0 };
}

export type SwitchAction =
  | { action: "ignore"; reason: string }
  | { action: "retry-same"; waitMs: number; reason: string }
  | { action: "switch"; to: ModelRef; thinking: "high"; message: string; reason: string }
  | { action: "handoff"; reason: string };

export interface SwitchInput {
  classified: ClassifiedError;
  current: ModelRef;
  memory: RunMemory;
  disabled: boolean;
  /** 跨 provider 回放不兼容时，由 compat.ts 改成先压缩。 */
  errorText: string;
}

function isPrimary(model: ModelRef): boolean {
  return model.provider === PRIMARY.provider && model.id === PRIMARY.id;
}

function isFallback(model: ModelRef): boolean {
  return model.provider === FALLBACK.provider && model.id === FALLBACK.id;
}

export function continueMessage(klass: string, errorText: string): string {
  const detail = errorText.trim().slice(0, 180) || klass;
  return [
    `[x-failover] 主模型 ${modelKey(PRIMARY.provider, PRIMARY.id)} 不可用（类别 ${klass}：${detail}）。`,
    `已切换到 ${modelKey(FALLBACK.provider, FALLBACK.id)}（thinking high）。请继续当前工作：`,
    "1) 先读 .work-docs/runs/<id>/capsule.md；2) 以 ledger 为准，不重做已 VERIFIED 的单元；",
    "3) 单次输出保持小块（大文件分段写），避免触达 16384 输出上限。",
  ].join("\n");
}

function handoffOrSwitch(memory: RunMemory, message: string, reason: string): SwitchAction {
  const withoutProgress =
    memory.toolCallsSinceFailover === 0 && memory.failovers > 0
      ? memory.failoversWithoutProgress + 1
      : 0;
  if (memory.failovers >= MAX_FAILOVERS_PER_RUN) {
    return { action: "handoff", reason: `failover 已达 ${MAX_FAILOVERS_PER_RUN} 次` };
  }
  if (withoutProgress >= MAX_FAILOVERS_WITHOUT_PROGRESS) {
    return { action: "handoff", reason: "连续 failover 后没有工具进展" };
  }
  return {
    action: "switch",
    to: { provider: FALLBACK.provider, id: FALLBACK.id },
    thinking: "high",
    message,
    reason,
  };
}

/**
 * 决定这一次 settle 要不要换模型。
 * 只在当前模型是 primary，或已经在 fallback 上处理第二级时生效。
 */
export function decideSwitch(input: SwitchInput): SwitchAction {
  const { classified, current, memory, disabled } = input;
  if (disabled) return { action: "ignore", reason: "x-failover off" };
  if (classified.klass === "E0" || classified.klass === "none") {
    return { action: "ignore", reason: classified.klass };
  }
  const onPrimary = isPrimary(current);
  const onFallback = isFallback(current);
  if (!onPrimary && !onFallback) return { action: "ignore", reason: "当前模型不是 primary 或 fallback" };

  if (classified.klass === "E4") {
    if (onFallback) return { action: "handoff", reason: "兜底模型出现 E4，停止以免循环" };
    return handoffOrSwitch(memory, continueMessage("E4", input.errorText), "primary E4");
  }

  if (classified.klass === "E2" && memory.sameModelRetries < 1) {
    return { action: "retry-same", waitMs: E2_RETRY_WAIT_MS, reason: "E2 同模型再试 1 次" };
  }

  if (onFallback && (classified.klass === "E3" || classified.klass === "E5") && memory.sameModelRetries < 1) {
    return { action: "retry-same", waitMs: 0, reason: "兜底模型 E3 先再试 1 次" };
  }

  if (onFallback) {
    return { action: "handoff", reason: "兜底模型仍然失败，第二兜底未启用" };
  }

  return handoffOrSwitch(
    memory,
    continueMessage(classified.klass, input.errorText),
    `切换 ${classified.klass}`,
  );
}

export function memoryAfter(memory: RunMemory, action: SwitchAction): RunMemory {
  if (action.action === "retry-same") {
    return { ...memory, sameModelRetries: memory.sameModelRetries + 1 };
  }
  if (action.action === "switch") {
    const withoutProgress =
      memory.toolCallsSinceFailover === 0 && memory.failovers > 0 ? memory.failoversWithoutProgress + 1 : 0;
    return {
      failovers: memory.failovers + 1,
      sameModelRetries: 0,
      failoversWithoutProgress: withoutProgress,
      toolCallsSinceFailover: 0,
    };
  }
  return memory;
}
