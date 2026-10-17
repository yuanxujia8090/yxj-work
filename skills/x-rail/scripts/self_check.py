#!/usr/bin/env python3
"""体量门禁和外部技能存在性。不调用模型。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ENTRY_MAX = 5 * 1024
STAGE_MAX = 6 * 1024
PAIR_MAX = 12 * 1024
STAGES = ("frame", "plan", "execute", "review", "land")
EXTERNAL = ("tdd", "code-review", "diagnosing-bugs", "research", "domain-modeling", "grilling", "codebase-design")


def fail(message: str) -> None:
    print(f"self_check: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_sizes(root: Path) -> None:
    skill = root / "skills" / "x-rail"
    entry = skill / "SKILL.md"
    if not entry.is_file():
        fail(f"缺少 {entry}")
    text = entry.read_text()
    if "disable-model-invocation:" in text.split("---", 2)[1]:
        fail("x-rail 入口不能设置 disable-model-invocation")
    entry_size = entry.stat().st_size
    if entry_size > ENTRY_MAX:
        fail(f"入口 {entry_size} 字节，上限 {ENTRY_MAX}")
    for name in STAGES:
        card = skill / "stages" / f"{name}.md"
        if not card.is_file():
            fail(f"缺少阶段卡 {card}")
        size = card.stat().st_size
        if size > STAGE_MAX:
            fail(f"{card.name} {size} 字节，上限 {STAGE_MAX}")
        if entry_size + size > PAIR_MAX:
            fail(f"入口加 {card.name} 共 {entry_size + size} 字节，上限 {PAIR_MAX}")
    print(f"self_check: 体量通过 入口={entry_size}")


def check_external(root: Path, skills_dir: Path | None) -> None:
    if skills_dir is None:
        print("self_check: 未指定外部技能目录，跳过存在性检查")
        return
    if not skills_dir.is_dir():
        print(f"self_check: 外部技能目录不存在，跳过存在性检查：{skills_dir}")
        return
    missing = [name for name in EXTERNAL if not (skills_dir / name / "SKILL.md").is_file()]
    if missing:
        fail("缺少外部技能 " + ", ".join(missing) + f"。它们应装在 {skills_dir}，x-rail 会调用它们，不要归档。")
    print(f"self_check: 外部技能齐全 {skills_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skills-dir", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    check_sizes(root)
    check_external(root, Path(args.skills_dir).resolve() if args.skills_dir else None)


if __name__ == "__main__":
    main()
