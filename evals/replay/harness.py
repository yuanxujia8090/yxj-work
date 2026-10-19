#!/usr/bin/env python3
"""R1–R7 回放台。默认只跑不花钱的控制流检查。--live 需要用户批准。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
XR = ROOT / "skills" / "x-rail" / "scripts" / "xr"
SCENARIOS = Path(__file__).with_name("scenarios.json")


def classify(text: str) -> str:
    script = r"""
import { classifyError } from "./classify.ts";
const text = process.argv[1];
console.log(classifyError({ text }).klass);
"""
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script, text],
        cwd=ROOT / "skills" / "x-rail" / "extensions",
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip().splitlines()[-1]


def xr(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(XR), "--repo", str(repo), *args], capture_output=True, text=True, env=merged)


def offline(scenarios: list[dict]) -> list[dict]:
    results = []
    for item in scenarios:
        name = item["id"]
        if name == "R3":
            klass = classify("The service is busy")
            ok = klass == "E2"
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": klass, "live": "pending-user-approval"})
        elif name == "R4":
            repo = Path(tempfile.mkdtemp())
            xr(repo, "init", "replay")
            run = repo / ".work-docs" / "runs" / (repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
            (repo / "README.md").write_text("x\n")
            xr(repo, "plan", "add", "u", "单元", "--deps", "none", "--files", "README.md", "--verify", "true")
            xr(repo, "next")
            xr(repo, "verify", "u")
            xr(repo, "done", "u")
            sizes = []
            for _ in range(6):
                proc = xr(repo, "capsule")
                sizes.append((run / "capsule.md").stat().st_size)
                if proc.returncode != 0:
                    break
            text = (run / "capsule.md").read_text()
            ok = all(size <= 2048 for size in sizes) and "u" in text
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": sizes, "live": "pending-user-approval"})
        elif name == "R5":
            repo = Path(tempfile.mkdtemp())
            xr(repo, "init", "cap")
            (repo / "README.md").write_text("x\n")
            xr(repo, "plan", "add", "u", "太大", "--deps", "none", "--files", "README.md", "--verify", "true")
            xr(repo, "next")
            proc = xr(repo, "fail", "u", "--kind", "cap", "--record", "replay:R5 oversized unit; host-run=none")
            units = list((repo / ".work-docs" / "runs").glob("*/units.tsv"))[0].read_text()
            ok = proc.returncode == 0 and "u\t太大\tabandoned\t" in units
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": proc.stdout.strip(), "live": "pending-user-approval"})
        elif name == "R6":
            repo = Path(tempfile.mkdtemp())
            xr(repo, "init", "crash")
            (repo / "README.md").write_text("x\n")
            xr(repo, "plan", "add", "u", "做到一半", "--deps", "none", "--files", "README.md", "--verify", "true")
            xr(repo, "next")
            status = xr(repo, "status")
            ok = "doing: 1" in status.stdout
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": "进程结束后磁盘仍是 doing", "live": "pending-user-approval"})
        elif name == "R7":
            repo = Path(tempfile.mkdtemp())
            xr(repo, "init", "parallel")
            for name_id, scope in (("a", "a.txt"), ("b", "a.txt"), ("c", "c.txt")):
                (repo / scope).write_text(scope)
                xr(repo, "plan", "add", name_id, name_id, "--deps", "none", "--files", scope, "--verify", "true")
            state = repo / "breaker.json"
            state.write_text(json.dumps({"version": 1, "breakers": {"openai26/gpt-6.1-sol": {"open": True}}, "runs": {}}))
            first = xr(repo, "next", env={"X_FAILOVER_STATE": str(state)})
            second = xr(repo, "next", env={"X_FAILOVER_STATE": str(state)})
            klass = classify("gateway_concurrency_limit")
            ok = "doing" in first.stdout and "none" in second.stdout and klass == "E1"
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": klass, "live": "pending-user-approval"})
        else:
            klass = classify(item["inject"])
            ok = klass == item["expectClass"]
            results.append({"id": name, "offline": "passed" if ok else "failed", "detail": klass, "live": "pending-user-approval"})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", default=str(Path(__file__).with_name("results.json")))
    args = parser.parse_args()
    if args.live and os.environ.get("XR_REPLAY_APPROVED") != "1":
        print("回放要调用真实模型，产生费用。设置 XR_REPLAY_APPROVED=1 后再运行 --live。本次不调用。", file=sys.stderr)
        return 2
    scenarios = json.loads(SCENARIOS.read_text())
    results = offline(scenarios)
    payload = {"live": "not-run", "results": results}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    failed = [item["id"] for item in results if item["offline"] != "passed"]
    print(json.dumps({"offline_failed": failed, "live": "pending-user-approval"}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
