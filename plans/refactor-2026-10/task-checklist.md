# x-rail 重构阶段3试点任务清单

**开始时间**: 2026-10-17  
**目标**: bugfix路径轻量化改造（阶段3已完成）  
**估算**: 4-6小时

---

## 任务状态

- [x] 1. 创建目录结构 (30分钟) - 已完成 2026-10-17 01:34
- [x] 2. 拆分SKILL.md (2小时) - 已完成
- [x] 3. 创建新格式模板 (1小时) - 已完成
- [x] 4. 修改playbooks/bugfix.md (30分钟) - 已完成
- [x] 5. 实现task.py check (2小时) - 已完成
- [x] 6. 真实bug测试 (1小时) - 已完成

---

## 步骤1: 创建目录结构 ✓ 已完成

**完成标准**:
- [x] modules/目录存在
- [x] 5个.md文件已创建

---

## 步骤2: 拆分SKILL.md ✓ 已完成

**目标**: 入口文件从25KB压缩到5KB

**操作**:
1. 备份旧版本
2. 从SKILL.md移出内容到modules/
3. 保留核心内容在SKILL.md

**完成标准**:
- [x] SKILL.md.bak已创建
- [x] modules/verification.md已填充
- [x] modules/execution.md已填充
- [x] modules/recovery.md已填充
- [x] modules/work-items.md已填充
- [x] modules/cost-policy.md已填充
- [x] SKILL.md < 5KB

---

## 步骤3-5：模板、playbook、检查器 ✓ 已完成

- `skills/x-rail/SKILL.md` 已压缩到目标以内
- 5 个 modules 已填充
- `templates/task-checklist.md` 已创建
- `task.py check <task-file>` 已支持 Markdown 清单，旧目录检查保持兼容
- 新增清单检查测试，既有任务/工作项回归通过

## 步骤6：真实 bug 试点 ✓ 已完成

- 旧版命令对 Markdown 清单复现失败：`contract.md not found or is a symlink`
- 新版命令对合法清单返回 `Result: PASSED`
- 结构、逻辑、证据三类反例分别返回退出码 1、2、3
- 试点记录：`plans/refactor-2026-10/pilot-task.md`

## 进度记录

| 时间 | 步骤 | 状态 | 备注 |
|------|------|------|------|
| 2026-10-17 01:32 | 启动阶段3 | 开始 | 批准通过 |
| 2026-10-17 01:34 | 步骤1 | 完成 | modules/目录和5个文件已创建 |
| 2026-10-17 01:35 | 步骤2 | 开始 | 准备拆分SKILL.md |
| 2026-10-17 02:xx | 步骤2-5 | 完成 | 入口、模块、模板、bugfix引用、check实现与回归完成 |
| 2026-10-17 02:xx | 步骤6 | 完成 | 真实旧版失败已复现，新版通过；5+72+17项测试通过 |
