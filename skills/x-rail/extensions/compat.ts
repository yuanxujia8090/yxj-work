import type { SwitchAction } from "./switch.ts";

export type PlannedSwitch = SwitchAction | { action: "compact-then-switch"; message: string; reason: string };

/** T3 失败时的退路：先压缩（内容用胶囊），再在兜底模型上续跑。 */
export function planSwitch(action: SwitchAction, replayCompatible: boolean): PlannedSwitch {
  if (action.action === "switch" && !replayCompatible) {
    return { action: "compact-then-switch", message: action.message, reason: "跨 provider 消息不兼容，先压缩再续跑" };
  }
  return action;
}
