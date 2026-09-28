# Handoff: yxj-work 独立工作流仓库

## 1. 任务目标

完成 `/Users/yuanxj/Documents/github/yxj-work` 独立工作流仓库，将新工作流与旧 `yxj-mode` 体系隔离：

- 新 skill：`yxj-work`、`yxj-work-long`、`yxj-work-handoff`
- 旧 skill 保持不变：
  - `/Users/yuanxj/.pi/agent/skills/yxj-mode/`
  - `/Users/yuanxj/.pi/agent/skills/yxj-mode-long/`
  - `/Users/yuanxj/.pi/agent/skills/yxj-handoff/`
- L1/L2/L3 工作流持久文件统一写入命令实际执行目录下唯一的 `.work-docs/`；本交接包因用户指定，位于源仓库的 `.work-docs/`。
- 不提交、不推送、不创建 PR，除非用户另行要求

## 2. 当前状态

- `status: blocked`
- `stage: verification / handoff`
- `blocked_by: final_verification_not_run_after_install_script_edit`
- 这不是功能设计阻塞，而是最后一次安装脚本编辑后的验证尚未完成。
- 当前不要把任务标记为 `done`。

## 3. 当前仓库内容

源仓库：`/Users/yuanxj/Documents/github/yxj-work`

已创建/更新：

- `README.md`
- `docs/architecture.md`
- `docs/file-boundary.md`
- `skills/yxj-work/SKILL.md`
- `skills/yxj-work/playbooks/`
  - `research.md`
  - `investigate.md`
  - `design.md`
  - `plan.md`
  - `exec.md`
  - `bugfix.md`
  - `review.md`
  - `ops.md`
  - `third-party-skill.md`
- `skills/yxj-work-long/SKILL.md`
- `skills/yxj-work-handoff/SKILL.md`
- `scripts/check-repo.sh`
- `scripts/install.sh`
- `scripts/check-workflow.sh`

仓库当前 Git 状态在暂停前显示这些文件均为未跟踪；当前分支为 `main`。不要自行提交。

## 4. 已完成的设计决定

1. `/Users/yuanxj/Documents/github/yxj-work` 是唯一事实源；`~/.pi/agent/skills/yxj-work*` 只能是安装副本。
2. 默认安装拒绝覆盖既有目录。
3. `--update` 只能更新带 `.yxj-work-installed` marker 且 marker 中 `source=` 与当前仓库路径一致的副本。
4. `.work-docs/tasks/<task-id>/` 包含 `contract.md`、`state.md`、`handoff.md`、`evidence/`、`outputs/`、`audit/`、`tmp/`。
5. 固定路径或未知写入的第三方 skill 必须隔离或阻塞。
6. `status: done` 只有在 required 验证全部 `passed`、required 子任务结束、无越界文件、决策门允许交付且所有结论有 evidence 时才允许。
7. 连续 3 次 required 验证失败、60 次工具调用无进展、30 分钟无有效进展、第三方越界写入或共同前提被否定时熔断。

## 5. 已有验证证据

详见：`/Users/yuanxj/Documents/github/yxj-work/.work-docs/tasks/20260928-01-yxj-work-independent-workflow/evidence/verification.md`

已通过：

- 方案章节检查：`计划章节齐全`
- 源仓库检查：`check-repo: passed`
- 临时安装：成功
- 安装副本一致性：`check-workflow: passed`
- `.work-docs` 路由 fixture：`work-docs fixture: passed`
- 熔断 checkpoint fixture：`circuit-breaker fixture: passed`
- 旧 skill 完整性清单：`/tmp/yxj-work-old-skills-after.sha256`，11 个文件

注意：以上安装相关成功结果发生在最后一次 `install.sh` 编辑之前，不能替代编辑后的最终验证。

## 6. 最后一次编辑的风险点

最后一次修改了：

`/Users/yuanxj/Documents/github/yxj-work/scripts/install.sh`

意图：让 `--update` 检查：

```bash
grep -Fqx "source=$ROOT" "$marker"
```

并拒绝更新属于其他源仓库的安装副本。

编辑过程中曾短暂产生重复 `rm/cp/done` 块，随后已删除；但必须先读取完整脚本确认：

- `marker="$dst/.yxj-work-installed"` 在使用前定义；
- `for skill ... do ... done` 只有一个闭合块；
- 没有重复复制块；
- shell 语法正确。

## 7. 下一步第一动作（必须先做）

```bash
cd /Users/yuanxj/Documents/github/yxj-work
sed -n '1,120p' scripts/install.sh
bash scripts/check-repo.sh
tmpdir="$(mktemp -d)"
bash scripts/install.sh --dest "$tmpdir"
bash scripts/check-workflow.sh \
  --source "$PWD" \
  --installed "$tmpdir"
```

如果这组命令失败：

1. 读取具体错误；
2. 只修复 `/Users/yuanxj/Documents/github/yxj-work/scripts/install.sh` 或相关新仓库文件；
3. 不触碰旧 `yxj-mode` 体系；
4. 修复后重跑源仓库检查、临时安装、副本一致性；
5. 连续 3 次 required 验证失败时停止并写入 `state.md` 的熔断字段，不得继续盲改。

如果通过，再重新运行 `.work-docs` 路由 fixture 和熔断 fixture。最后可将 `state.md` 更新为 `status: done`，但前提是所有 required evidence 都已更新到最后一次编辑之后。

## 8. 关键约束

- 不要把 handoff 复制到其他目录；当前交接包固定在源仓库 `.work-docs/tasks/20260928-01-yxj-work-independent-workflow/`。
- 不要写入 `00-Inbox/`、Wiki、项目 docs、外部 `local://` 或外部 `.audit/`。
- 不要手工编辑安装后的 `~/.pi/agent/skills/yxj-work*` 副本；只改源仓库后通过安装脚本安装。
- 不要修改、移动、删除或重命名旧 skill。
- 不要未经要求 commit、push、创建 PR。

## 9. 交接入口

新 Agent 首先读取：

1. 本文件：`/Users/yuanxj/Documents/github/yxj-work/.work-docs/tasks/20260928-01-yxj-work-independent-workflow/handoff.md`
2. 同目录的 `state.md`
3. 同目录的 `contract.md`
4. 同目录的 `evidence/verification.md`
5. `/Users/yuanxj/Documents/github/yxj-work/scripts/install.sh`

然后执行第 7 节的第一动作。
