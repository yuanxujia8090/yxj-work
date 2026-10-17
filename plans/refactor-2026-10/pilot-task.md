# Task: refactor-2026-10-pilot

## Meta

- Created: 2026-10-17T02:20:00Z
- Status: done
- Type: bugfix

## Intent

- Goal: 修复 `task.py check` 无法检查 Markdown 任务清单的问题
- Scope: `skills/x-rail/scripts/task.py`、`skills/x-rail/scripts/task_checks.py`
- Done when: 目录任务检查保持兼容，Markdown 清单检查通过，反例返回对应错误码

## Checklist

- [x] 1. 复现旧检查器对 Markdown 清单的失败 — evidence: E1
- [x] 2. 验证新检查器通过合法清单 — evidence: E2
- [x] 3. 验证既有目录检查和回归测试 — evidence: E3

## Evidence

### E1: 旧检查器复现

- Command: `git show HEAD:skills/x-rail/scripts/task.py` 版本检查 Markdown 清单
- Exit: 1
- Result: FAILED（`contract.md not found or is a symlink`）
- Path: pilot-old-output.txt
- Timestamp: 2026-10-17T02:18:00Z

### E2: 新检查器验证

- Command: `python3 skills/x-rail/scripts/task.py check plans/refactor-2026-10/pilot-task.md`
- Exit: 0
- Result: PASSED（Structure、Logic、Evidence 均通过）
- Path: pilot-new-output.txt
- Timestamp: 2026-10-17T02:21:00Z

### E3: 回归验证

- Command: `python3 scripts/test-task-checklist.py && python3 scripts/test-task-checks.py && python3 scripts/test-work-items.py`
- Exit: 0
- Result: PASSED（6 + 72 + 17 项测试通过）
- Path: pilot-regression-output.txt
- Timestamp: 2026-10-17T02:22:00Z

## Decisions

### D1: 保留旧目录检查接口

- Decision: `task.py check` 接收目录时继续执行原 contract/state 检查，接收文件时执行 Markdown 清单检查
- Reason: 保留已有任务和脚本调用兼容性
- Alternatives: 替换旧检查入口，风险更高且没有必要

### D2: 使用“证据模式”作为新称呼

- Decision: 新文档称“证据模式”，旧“严格记录/严格验证”字段兼容保留
- Reason: 直接说明证据绑定和恢复机制，降低概念负担
- Alternatives: 删除证据绑定机制，不采纳

## Next

- Action: 交付阶段3试点结果
- Then: 后续如需全面迁移，另行批准阶段4
