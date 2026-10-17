#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XR = ROOT / "skills" / "x-rail" / "scripts" / "xr"


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(XR), "--repo", str(repo), *args], capture_output=True, text=True)


class XrTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "README.md").write_text("seed\n")
        os.chmod(XR, 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def init(self) -> str:
        result = run(self.repo, "init", "demo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.split()[-1]

    def test_preflight_and_cycle_and_frontier(self):
        run_id = self.init()
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        text = (run_dir / "RUN.md").read_text()
        self.assertIn("python3:", text)
        self.assertIn("本地 wip", text)
        bad = run(self.repo, "plan", "add", "a", "A", "--deps", "b", "--files", "README.md", "--verify", "true")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("正确命令", bad.stdout)
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        cycle = run(self.repo, "plan", "add", "b", "B", "--deps", "a", "--files", "README.md", "--verify", "true")
        self.assertEqual(cycle.returncode, 0, cycle.stdout)
        back = run(self.repo, "plan", "add", "a", "A", "--deps", "b", "--files", "README.md", "--verify", "true")
        self.assertNotEqual(back.returncode, 0)
        self.assertIn("环", back.stdout)

    def test_overlap_verify_done_and_fail(self):
        self.init()
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.txt").write_text("a\n")
        (self.repo / "src" / "b.txt").write_text("b\n")
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "src/a.txt", "--verify", "true").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "b", "B", "--deps", "none", "--files", "src/a.txt", "--verify", "true").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "c", "C", "--deps", "none", "--files", "src/b.txt", "--verify", "true").returncode, 0)
        first = run(self.repo, "next")
        self.assertIn("ok next a doing", first.stdout)
        second = run(self.repo, "next")
        self.assertIn("ok next c doing", second.stdout)
        third = run(self.repo, "next")
        self.assertIn("ok next none", third.stdout)
        early = run(self.repo, "done", "a")
        self.assertNotEqual(early.returncode, 0)
        self.assertIn("xr verify a", early.stdout)
        verified = run(self.repo, "verify", "a")
        self.assertIn("VERIFIED", verified.stdout)
        again = run(self.repo, "verify", "a")
        self.assertIn("cached", again.stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        self.assertIn("unchanged", run(self.repo, "done", "a").stdout)
        failed = run(self.repo, "fail", "c", "--kind", "cap")
        self.assertEqual(failed.returncode, 0, failed.stdout)
        self.assertIn("abandoned", failed.stdout)
        self.assertNotIn("doing", failed.stdout.splitlines()[0])
        units = (self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip() / "units.tsv").read_text()
        self.assertIn("abandoned", units)
        self.assertNotRegex(units, r"^c\t.*\tdoing\t", )

    def test_status_idempotent_capsule_and_import(self):
        run_id = self.init()
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        (run_dir / "RUN.md").write_text((run_dir / "RUN.md").read_text().replace("（写可数、可检查的完成判据）", "X" * 8000))
        self.assertEqual(run(self.repo, "status").returncode, 0)
        before = (run_dir / "RUN.md").read_text()
        second = run(self.repo, "status")
        self.assertIn("unchanged", second.stdout)
        self.assertEqual(before, (run_dir / "RUN.md").read_text())
        capsule = run(self.repo, "capsule")
        self.assertEqual(capsule.returncode, 0, capsule.stdout)
        blob = (run_dir / "capsule.md").read_bytes()
        self.assertLessEqual(len(blob), 2048)
        self.assertIn(b"Done", blob)
        self.assertIn("下一步".encode(), blob)
        task = self.repo / ".work-docs" / "tasks" / "old-1"
        task.mkdir(parents=True)
        contract = task / "contract.md"
        state = task / "state.md"
        contract.write_text("task_id: old-1\nobjective: 旧目标\nwork_item:w1|title=旧项|requirements=R|depends=none|scope=README.md|required=yes|acceptances=A1|skip_reason=none\n")
        state.write_text("status: in_progress\n")
        hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (contract, state)}
        imported = run(self.repo, "import", "old-1")
        self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
        self.assertEqual(hashes[contract], hashlib.sha256(contract.read_bytes()).hexdigest())
        self.assertEqual(hashes[state], hashlib.sha256(state.read_bytes()).hexdigest())
        self.assertIn("units=", imported.stdout)

    def test_gate_decide_and_bad_verb(self):
        self.init()
        self.assertEqual(run(self.repo, "decide", "用 TSV", "--why", "脚本写状态").returncode, 0)
        again = run(self.repo, "decide", "用 TSV", "--why", "脚本写状态")
        self.assertIn("unchanged", again.stdout)
        self.assertEqual(run(self.repo, "plan", "add", "g", "G", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertIn("ok gate", run(self.repo, "gate", "要不要改接口", "--default", "不改", "--unit", "g").stdout)
        self.assertIn("unchanged", run(self.repo, "gate", "要不要改接口", "--default", "不改", "--unit", "g").stdout)
        bad = run(self.repo, "nope")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("正确命令", bad.stdout)
        missing = run(self.repo, "plan", "add")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("xr plan add", missing.stdout)

    def test_subagent_mode_and_halved_concurrency(self):
        self.init()
        for name in ("a", "b", "c", "d", "e"):
            path = f"f-{name}.txt"
            (self.repo / path).write_text(name)
            result = run(self.repo, "plan", "add", name, name, "--deps", "none", "--files", path, "--verify", "true")
            self.assertEqual(result.returncode, 0, result.stdout)
            if name == "e":
                self.assertIn("mode=subagents", result.stdout)
        state = self.repo / "breaker.json"
        state.write_text(json.dumps({"version": 1, "disabled": False, "breakers": {"openai26/gpt-6.1-sol": {"open": True}}, "runs": {}}))
        env = os.environ.copy()
        env["X_FAILOVER_STATE"] = str(state)
        claimed = []
        for _ in range(4):
            result = subprocess.run([str(XR), "--repo", str(self.repo), "next"], capture_output=True, text=True, env=env)
            claimed.append(result.stdout.strip())
        doing = [line for line in claimed if " doing" in line]
        self.assertEqual(len(doing), 1)


if __name__ == "__main__":
    unittest.main()
