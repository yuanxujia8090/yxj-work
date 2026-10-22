#!/usr/bin/env python3
"""技能体积检查：把 v3 的四道体积上限固化成可执行检查。

口径与 v3 `plans/0.0.7/体积基线与验收.md` 一致：
- 原始字节，按文件计，排除 node_modules/.git/__pycache__/.venv/dist/build；
- 不跟随目录符号链接；
- 说明文档统计 `.md`；代码统计 `.py/.ts/.js/.mjs/.sh` 与无后缀的 `xr`；
- 代码只记录不设上限（v3 明确：代码与测试允许为必要保障增长，需列职责与反例）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXCLUDED = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}
CODE_SUFFIXES = {".py", ".ts", ".js", ".mjs", ".sh"}


def collect(skill: Path) -> list[Path]:
    files = []
    for path in sorted(skill.rglob("*")):
        if not path.is_file():
            continue
        if set(path.relative_to(skill).parts) & EXCLUDED:
            continue
        files.append(path)
    return files


def size(path: Path) -> int:
    return len(path.read_bytes())


def measure(skill: Path, run_docs: list[str]) -> dict[str, int]:
    files = collect(skill)
    docs = [path for path in files if path.suffix == ".md"]
    code = [path for path in files if path.suffix in CODE_SUFFIXES or path.name == "xr"]
    stages_refs = [path for path in docs if path.relative_to(skill).parts[0] in {"stages", "references"}]
    skill_md = skill / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"check-size: 缺少 {skill_md}")
    return {
        "skill_md_bytes": size(skill_md),
        "run_docs_bytes": sum(size(skill / name) for name in run_docs),
        "stages_references_bytes": sum(size(path) for path in stages_refs),
        "all_docs_bytes": sum(size(path) for path in docs),
        "code_bytes": sum(size(path) for path in code),
        "docs_files": len(docs),
        "code_files": len(code),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="仓库根目录")
    parser.add_argument("--budget", default=None, help="预算 JSON，默认 scripts/size-budget.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    budget_path = Path(args.budget) if args.budget else root / "scripts/size-budget.json"
    try:
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"check-size: 预算文件读不了：{budget_path}（{error}）", file=sys.stderr)
        return 1
    skill = root / budget["skill"]
    if not skill.is_dir():
        print(f"check-size: 找不到技能目录 {skill}", file=sys.stderr)
        return 1

    actual = measure(skill, budget["run_docs"])
    limits = budget["limits"]
    failures = []

    for key, limit in limits.items():
        got = actual[key]
        if got > limit:
            failures.append((key, got, limit))
    # 代码不设上限，但要显式记录，避免“体积合格”掩盖代码膨胀。
    record_only = budget.get("record_only", {}).get("code_bytes")

    if args.json:
        print(json.dumps({"actual": actual, "limits": limits, "failures": failures}, ensure_ascii=False))
    else:
        print(f"check-size: {budget['skill']}")
        for key, limit in limits.items():
            print(f"  {key}: {actual[key]} / {limit}")
        print(f"  code_bytes: {actual['code_bytes']}（仅记录，不设上限）")
        if record_only is not None and actual["code_bytes"] != record_only:
            print(f"  code_bytes 变化: {actual['code_bytes'] - record_only:+d}（需在交付说明列出新增职责）")

    if failures:
        for key, got, limit in failures:
            print(f"check-size: 超限 {key} = {got} > {limit}", file=sys.stderr)
        return 1
    print("check-size: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
