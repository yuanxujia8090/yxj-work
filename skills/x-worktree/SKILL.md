---
name: x-worktree
description: 用户主动调用时，在当前项目里创建一个同名分支工作区（.worktrees/<名称>），并把主分支目录的 .env.local 复制进去。用于并行开发、隔离试验或避免在主分支直改。
disable-model-invocation: true
---

# x-worktree

## File boundary

The workflow root is the directory this skill runs in (`<execution-root>`). Every durable file this skill
generates goes under:

```text
<execution-root>/.work-docs/tasks/<task-id>/
├── contract.md   what done means, allowed changes, verification layers
├── state.md      stage, status, evidence pointers, blockers
├── outputs/      final reports, designs, plans, manuals
├── evidence/     command output, measurements, failure evidence
├── audit/        decisions, checkpoints, work-in-progress records
└── tmp/          fixtures and disposable material
```

Reuse the task id already in progress when the scope matches (read `.work-docs/index.md` first), otherwise
allocate one: `{YYYYMMDD}-{NN}-{slug}`, where `NN` is a two-digit per-day counter that
restarts at `01` and never reuses a retired number, then append the new task to `.work-docs/index.md`.
Never place workflow output in a project docs directory, in another skill's directory, in a
tool-specific hidden directory, or outside the repository.

Files that are themselves the task target -- project code, project docs, existing config -- may be modified
in place. Record those paths in the contract and in `evidence/` before changing them, and do not copy them
into `.work-docs`. Before running any third-party skill that writes files, take a before/after inventory; a
write outside `.work-docs` that the contract did not authorize is a boundary violation: stop and report it.

例外：本技能的主要产物是 git 工作区与分支，它们按用户要求落在项目的 `.worktrees/<名称>`（可用 `--dir` 改）。这些不是 `.work-docs` 记录；如果本次在 x-rail 任务里，把工作区路径和分支名写进契约与 `evidence/`。

## 做什么

用户敲：

```text
/x-worktree 我的特性名
/x-worktree              # 不写名称时用 feat-{YYYYMMDDHHmmss}
```

然后按固定三步执行，形成结论后才回复：

1. **找主分支**。读本地分支：有 `main` 用 `main`，否则有 `master` 用 `master`；都没有就看 `origin/HEAD`；仍然没有就停下，请用户用 `--main <分支>` 点名。
2. **建工作区**。在项目的 `.worktrees/<名称>` 下创建同名分支的工作区，基点是指定的主分支。
3. **复制环境文件**。把**主分支所在目录**的 `.env.local` 复制到新工作区。主分支目录用 `git worktree list` 定位；源文件不存在就跳过并说明，不当失败。

一条命令完成，脚本自己判断和拒绝：

```bash
bash <skill-dir>/scripts/create_worktree.sh [名称] [--main 分支] [--dir 目录]
```

参数：

| 参数 | 含义 | 默认 |
|---|---|---|
| 名称 | 分支名，也是目录名 | `feat-{YYYYMMDDHHmmss}` |
| `--main` | 指定基点分支 | 自动识别 main / master |
| `--dir` | 新工作区所在的目录，相对仓库根 | `.worktrees` |

退出码：`0` 成功；`1` 分支或目录已存在（不覆盖，换名字）；`2` 参数、环境或 git 错误。

## 行为约束

- 新工作区固定建在**主工作区**（`git worktree list` 的第一条）下的 `.worktrees/`，从子工作区里运行也一样。这样工作区不会互相嵌套。
- 分支是本地新建，不跟踪远端，不 push，不提交。
- 只复制 `.env.local` 这一个文件，不复制其他未跟踪文件。
- 已存在的分支或目录一律拒绝，不覆盖、不删除、不加 `--force`。
- 只读判断：先看 `git branch` / `git worktree list` 的真实输出再动手；名字冲突时报告冲突，不问「要不要覆盖」。

## 复制的是密钥文件

`.env.local` 通常含密钥。本技能只在本机项目目录之间复制，不打印内容、不写进日志、不提交。回复里只写「已复制自哪个路径」，不贴文件内容。若新目录会被推送到远端或共享，先提醒用户。

## 收尾时报告

一行路径与分支，加三条事实：

- 工作区路径、分支名、基点提交
- `.env.local` 是否复制，来源目录
- `.worktrees/<名称>` 未被 `.gitignore` 忽略时，提示这一条（是否加进忽略由用户决定，本技能不改项目文件）

## 验证

```bash
bash scripts/test-worktree.sh
```

测试在临时仓库里真的执行 `git worktree add`，断言：默认名称格式、分支与目录建立、`.env.local` 复制、从子工作区运行仍取主分支目录、重名退出 1、非法名称与找不到主分支退出 2、`--main` 与 `--dir` 生效、没有 `.env.local` 时不失败。

## 不做什么

- 不清理、不删除既有工作区或分支。要删得由用户点名，并用 `git worktree remove`。
- 不创建远端分支，不推送，不合并。
- 不装依赖、不跑构建、不改项目文件（包括 `.gitignore`）。
- 不替代 `git worktree` 的其他用法（如基于远端分支签出、修复损坏的工作区）。
