/** 04 §2。按固定顺序把一条 provider 错误分到 E0–E5。 */

export type ErrorClass = "E0" | "E1" | "E2" | "E3" | "E4" | "E5" | "none";

export interface ClassifiedError {
  klass: ErrorClass;
  matched: string;
  /** 立刻换模型，并打开熔断。 */
  immediateFailover: boolean;
  /** 先在同一模型上再跑一次。 */
  sameModelRetry: boolean;
}

export interface ClassifyInput {
  stopReason?: string;
  text?: string;
  status?: number;
  /** 看门狗调用了 abort。这时 stopReason 往往是 aborted，仍按 E5。 */
  watchdog?: boolean;
  provider?: string;
}

const E1: RegExp[] = [
  /账号池暂无可用账号/,
  /gateway_concurrency_limit/,
  /INSUFFICIENT_BALANCE/,
  /insufficient_quota/,
  /\bbilling\b/i,
  /HTTP\s*401\b/,
  /HTTP\s*403\b/,
  /\bstatus\s*401\b/i,
  /\bstatus\s*403\b/i,
  /Server requested \d+s retry delay \(max: 80s\)/,
];

const E2: RegExp[] = [
  /The service is temporarily unavailable/,
  /The service is busy/,
  /Upstream stream ended prematurely/,
  /stream disconnected/i,
  /upstream_error/,
];

const E3: RegExp[] = [
  /Request timed out/,
  /HTTP\s*524\b/,
  /\bterminated\b/,
  /Connection error/i,
  /ECONNRESET/,
  /socket hang up/i,
];

const E4: RegExp[] = [
  /unknown variant ['"]developer['"]/,
  /\b422\b/,
  /bad request/i,
];

function hit(text: string, patterns: RegExp[]): string | null {
  for (const pattern of patterns) {
    const found = pattern.exec(text);
    if (found) return found[0];
  }
  return null;
}

export function classifyError(input: ClassifyInput): ClassifiedError {
  const text = input.text ?? "";
  if (input.watchdog) {
    return { klass: "E5", matched: "watchdog", immediateFailover: true, sameModelRetry: false };
  }
  if (input.stopReason === "aborted") {
    return { klass: "E0", matched: "aborted", immediateFailover: false, sameModelRetry: false };
  }
  if (input.status === 401 || input.status === 403) {
    return { klass: "E1", matched: String(input.status), immediateFailover: true, sameModelRetry: false };
  }
  const e1 = hit(text, E1);
  if (e1) return { klass: "E1", matched: e1, immediateFailover: true, sameModelRetry: false };
  const e2 = hit(text, E2);
  if (e2) return { klass: "E2", matched: e2, immediateFailover: false, sameModelRetry: true };
  const e3 = hit(text, E3);
  if (e3) return { klass: "E3", matched: e3, immediateFailover: true, sameModelRetry: false };
  const e4 = hit(text, E4);
  if (e4 || (input.status !== undefined && input.status >= 400 && input.status < 500)) {
    return {
      klass: "E4",
      matched: e4 || String(input.status),
      immediateFailover: false,
      sameModelRetry: false,
    };
  }
  return { klass: "none", matched: "", immediateFailover: false, sameModelRetry: false };
}

/** 从助手消息里抽出分类用的文本。不依赖 pi 的运行时。 */
export function assistantErrorText(message: unknown): { stopReason?: string; text: string } {
  if (!message || typeof message !== "object") return { text: "" };
  const record = message as Record<string, unknown>;
  const stopReason = typeof record.stopReason === "string" ? record.stopReason : undefined;
  const parts: string[] = [];
  if (typeof record.errorMessage === "string") parts.push(record.errorMessage);
  // 只有出错的回合才看正文。正常完成（stop / toolUse / length）的回答里出现
  // “HTTP 401”“Connection error”等字样，多半是在讨论代码，不是模型故障。
  if (stopReason !== undefined && stopReason !== "error") return { stopReason, text: parts.join("\n") };
  const content = record.content;
  if (typeof content === "string") parts.push(content);
  else if (Array.isArray(content)) {
    for (const item of content) {
      if (item && typeof item === "object" && typeof (item as Record<string, unknown>).text === "string") {
        parts.push((item as Record<string, unknown>).text as string);
      }
    }
  }
  return { stopReason, text: parts.join("\n") };
}
