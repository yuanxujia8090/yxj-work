#!/usr/bin/env python3
"""Safe task lifecycle commands."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_checks


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def complete(task_dir: Path, candidate: Path, before_commit=None) -> None:
    task_dir = Path(task_dir).resolve()
    candidate = Path(candidate)
    if not inside(candidate, task_dir) or candidate.resolve() == (task_dir / "state.md").resolve():
        raise ValueError("candidate must be a distinct file inside task directory")
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("candidate must be a regular file")
    formal = task_dir / "state.md"
    contract = task_dir / 'contract.md'
    if formal.is_symlink() or contract.is_symlink():
        raise ValueError('formal state and contract must not be symlinks')
    original = formal.read_bytes()
    original_contract = contract.read_bytes()
    candidate_bytes = candidate.read_bytes()
    if candidate.stat().st_dev != formal.stat().st_dev:
        raise ValueError('candidate must use the same filesystem')
    result = task_checks.check_state(task_dir, candidate)
    if result['status'] != 'done':
        raise ValueError('candidate must set status: done')
    if before_commit:
        before_commit()
    if formal.read_bytes() != original or contract.read_bytes() != original_contract or candidate.read_bytes() != candidate_bytes:
        raise ValueError("state, contract or candidate changed before commit")
    task_checks.check_state(task_dir, candidate)
    os.replace(candidate, formal)
    index = task_dir.parent.parent / 'index.md'
    if index.is_file():
        try:
            import re
            text = index.read_text()
            text = re.sub(r'(\| ' + re.escape(task_dir.name) + r' \|[^\n]*?\| )in_progress( \|)', r'\1done\2', text)
            index.write_text(text)
        except OSError as error:
            print(f'task: completed; index repair needed: {error}', file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["seal", "check"]:
        p = sub.add_parser(name)
        p.add_argument("task_dir")
    p = sub.add_parser("complete")
    p.add_argument("task_dir")
    p.add_argument("--candidate", required=True)
    args = parser.parse_args()
    try:
        task_dir = Path(args.task_dir).resolve()
        if args.command == "seal":
            task_checks.check_contract(task_dir, mode="seal")
        elif args.command == "check":
            task_checks.check_contract(task_dir, mode="locked")
            task_checks.check_state(task_dir)
        else:
            candidate = Path(args.candidate)
            complete(task_dir, candidate)
        print(f"task: {args.command} passed")
        return 0
    except (OSError, ValueError) as error:
        print(f"task: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
