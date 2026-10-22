#!/usr/bin/env python3
"""Check the historical scenario matrix and its stated coverage boundaries."""
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
report_path = root / "plans/v4/evidence/subagent-session-scenarios-2026-10.md"
template_path = root / "skills/x-rail/templates/child-task.md"
report = report_path.read_text()
template = template_path.read_text()

scenario_ids = re.findall(r"\| ([SO]\d+) ", report)
expected_ids = [f"S{i}" for i in range(1, 9)] + [f"O{i}" for i in range(1, 4)]
assert scenario_ids == expected_ids, f"scenario IDs/order mismatch: {scenario_ids}"
assert report.count("| 场景 | 日志中的失败 | v4 现有能力 | 评估 | 证据边界 |") == 1
for boundary in ["仍是提示规则", "不能离线断言真实代理存在", "不能观察模型是否遵守", "真实 Pi 调用效果未验证"]:
    assert boundary in report, f"coverage boundary missing: {boundary}"
for rule in [
    "单代理用顶层 `agent`/`task`；工作流需同回复脚本块，不混用",
    "仅确认未启动的拒绝可修正后重发",
    "其他错误先查原运行",
    "不重复派发",
]:
    assert rule in template, f"launch/recovery rule missing: {rule}"

print(f"test-subagent-scenarios: passed ({len(expected_ids)} scenarios, coverage limits and launch rules)")
