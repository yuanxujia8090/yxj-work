#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
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
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("ok next c doing", run(self.repo, "next").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        early = run(self.repo, "done", "a")
        self.assertNotEqual(early.returncode, 0)
        self.assertIn("xr verify a", early.stdout)
        verified = run(self.repo, "verify", "a")
        self.assertIn("VERIFIED", verified.stdout)
        again = run(self.repo, "verify", "a")
        self.assertIn("cached", again.stdout)
        failed_verify = run(self.repo, "fail", "a", "--kind", "verify", "--record", "error:verify;run:run-a;report:notes/a.md")
        self.assertEqual(failed_verify.returncode, 0, failed_verify.stdout)
        run_dir = self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        blocked_rows = (run_dir / "units.tsv").read_text()
        self.assertIn("\na\tA\tblocked", blocked_rows)
        self.assertIn("none;kind:verify", blocked_rows)
        self.assertIn("error:verify", blocked_rows)
        self.assertNotIn("ok next a doing", run(self.repo, "next").stdout)
        terminated = run(self.repo, "reopen", "a", "--resolution", "terminated", "--record", "host-run:terminated")
        self.assertEqual(terminated.returncode, 0, terminated.stdout)
        changed = run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "src/a.txt", "--verify", "false")
        self.assertEqual(changed.returncode, 0, changed.stdout + changed.stderr)
        rerun = run(self.repo, "verify", "a")
        self.assertIn("FAILED", rerun.stdout)
        self.assertNotIn("cached", rerun.stdout)
        self.assertNotEqual(run(self.repo, "done", "a").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "src/a.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        again_done = run(self.repo, "done", "a")
        self.assertEqual(again_done.returncode, 0, again_done.stdout)
        self.assertNotIn("unchanged", again_done.stdout)
        failed = run(self.repo, "fail", "c", "--kind", "cap", "--record", "error:cap;run:run-c")
        self.assertEqual(failed.returncode, 0, failed.stdout)
        terminal_fail = run(self.repo, "fail", "c", "--kind", "net", "--record", "error:net;run:run-c")
        self.assertNotEqual(terminal_fail.returncode, 0)
        self.assertIn("reopen", terminal_fail.stdout)
        self.assertIn("abandoned", failed.stdout)
        self.assertNotIn("doing", failed.stdout.splitlines()[0])
        units = (self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip() / "units.tsv").read_text()
        self.assertIn("abandoned", units)
        self.assertNotRegex(units, r"^c\t.*\tdoing\t")
        self.assertEqual(run(self.repo, "reopen", "c", "--resolution", "terminated", "--record", "host-run:terminated").returncode, 0)

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
        self.assertEqual(blob.count("模型：".encode()), 1)
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

    def test_close_and_safe_import_id(self):
        self.init()
        bad = run(self.repo, "import", "../outside")
        self.assertNotEqual(bad.returncode, 0)
        closed = run(self.repo, "close")
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)
        self.assertFalse((self.repo / ".work-docs" / "runs" / "ACTIVE").exists())

    def test_gate_decide_and_bad_verb(self):
        run_id = self.init()
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        self.assertEqual(run(self.repo, "decide", "用 TSV", "--why", "脚本写状态").returncode, 0)
        again = run(self.repo, "decide", "用 TSV", "--why", "脚本写状态")
        self.assertIn("unchanged", again.stdout)
        self.assertEqual(run(self.repo, "plan", "add", "g", "G", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertIn("ok gate", run(self.repo, "gate", "add", "要不要改接口", "--default", "不改", "--unit", "g").stdout)
        self.assertIn("unchanged", run(self.repo, "gate", "add", "要不要改接口", "--default", "不改", "--unit", "g").stdout)
        gate_bypass = run(self.repo, "reopen", "g", "--resolution", "terminated", "--record", "host-run:terminated")
        self.assertNotEqual(gate_bypass.returncode, 0)
        self.assertIn("blocked", (run_dir / "units.tsv").read_text())
        gates = (run_dir / "gates.md").read_text()
        self.assertEqual(gates.count("## G1\n"), 1)
        before = gates
        rejected = run(self.repo, "gate", "add", "不能改已完成", "--default", "跳过", "--unit", "missing")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(before, (run_dir / "gates.md").read_text())
        resolved = run(self.repo, "gate", "resolve", "G10", "--default")
        self.assertNotEqual(resolved.returncode, 0)
        self.assertIn("\ng\tG\tblocked\t", (run_dir / "units.tsv").read_text())
        resolved_gate = run(self.repo, "gate", "resolve", "G1", "--default")
        self.assertEqual(resolved_gate.returncode, 0, resolved_gate.stdout)
        self.assertIn("\ng\tG\tblocked\t", (run_dir / "units.tsv").read_text())
        resolved_unit = run(self.repo, "reopen", "g", "--resolution", "terminated", "--record", "host-run:terminated")
        self.assertEqual(resolved_unit.returncode, 0, resolved_unit.stdout)
        self.assertIn("\ng\tG\ttodo\t", (run_dir / "units.tsv").read_text())
        bad = run(self.repo, "nope")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("正确命令", bad.stdout)
        missing = run(self.repo, "plan", "add")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("xr plan add", missing.stdout)

    def test_blocked_failure_keeps_overlapping_write_scope_occupied(self):
        self.init()
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "b", "B", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        gated = run(self.repo, "gate", "add", "release decision", "--default", "stop", "--unit", "a")
        self.assertEqual(gated.returncode, 0, gated.stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        failed = run(self.repo, "fail", "a", "--kind", "net", "--record", "error:network;run:host-1")
        self.assertIn("blocked", failed.stdout)
        cap_again = run(self.repo, "fail", "a", "--kind", "cap", "--record", "error:cap;run:host-1")
        self.assertNotEqual(cap_again.returncode, 0)
        self.assertIn("blocked", (self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip() / "units.tsv").read_text())
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "unrelated.txt").write_text("independent")
        self.assertEqual(run(self.repo, "plan", "add", "c", "C", "--deps", "none", "--files", "src/unrelated.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next c doing", run(self.repo, "next").stdout)
        self.assertNotEqual(run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active").returncode, 0)
        resolved_gate = run(self.repo, "gate", "resolve", "G1", "--default")
        self.assertEqual(resolved_gate.returncode, 0, resolved_gate.stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        resumed = run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active")
        self.assertIn("doing", resumed.stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)

    def test_resuming_writer_respects_capacity_and_scope(self):
        self.init()
        (self.repo / "src").mkdir()
        for name in ("a", "b", "c"):
            (self.repo / "src" / f"{name}.txt").write_text(name)
            self.assertEqual(run(self.repo, "plan", "add", name, name, "--deps", "none", "--files", f"src/{name}.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("ok next b doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "a", "--kind", "net", "--record", "error:net;run:host-a").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        resumed = run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active")
        self.assertEqual(resumed.returncode, 0, resumed.stdout)

    def test_blocked_units_count_toward_reader_and_writer_limits(self):
        # Reader and total limits currently match (5/5, breaker 2/2); reader-only rejection is not independently distinguishable.
        self.init()
        for name, kind in (("w1", "impl"), ("w2", "impl"), ("w3", "impl"), ("r1", "review"), ("r2", "research"), ("r3", "review")):
            self.assertEqual(run(self.repo, "plan", "add", name, name, "--deps", "none", "--files", f"{name}.txt", "--verify", "true", "--kind", kind).returncode, 0)
        self.assertIn("ok next w1 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next w2 doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "w1", "--kind", "net", "--record", "run:w1").stdout)
        self.assertIn("ok next r1 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next r2 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next r3 doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "r1", "--kind", "net", "--record", "run:r1").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "r2", "--kind", "net", "--record", "run:r2").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "r3", "--kind", "net", "--record", "run:r3").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)

    def test_resuming_reader_respects_reader_limit(self):
        self.init()
        for name in ("r1", "r2", "r3", "r4"):
            self.assertEqual(run(self.repo, "plan", "add", name, name, "--deps", "none", "--files", f"{name}.txt", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertIn("ok next r1 doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "r1", "--kind", "net", "--record", "run:r1").stdout)
        self.assertIn("ok next r2 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next r3 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next r4 doing", run(self.repo, "next").stdout)
        breaker = self.repo / "breaker.json"
        breaker.write_text(json.dumps({"version": 1, "disabled": False, "breakers": {"test": {"open": True}}, "runs": {}}))
        env = os.environ.copy()
        env["X_FAILOVER_STATE"] = str(breaker)
        blocked = subprocess.run([str(XR), "--repo", str(self.repo), "fail", "r2", "--kind", "net", "--record", "run:r2"], capture_output=True, text=True, env=env)
        self.assertIn("blocked", blocked.stdout)
        resumed = subprocess.run([str(XR), "--repo", str(self.repo), "reopen", "r1", "--resolution", "resumed", "--record", "host:still-active"], capture_output=True, text=True, env=env)
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("额度", resumed.stdout)

    def test_readers_can_share_inputs_but_not_with_writers(self):
        self.init()
        self.assertEqual(run(self.repo, "plan", "add", "r1", "Review one", "--deps", "none", "--files", "README.md", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "r2", "Review two", "--deps", "none", "--files", "README.md", "--verify", "true", "--kind", "research").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "w", "Write", "--deps", "none", "--files", "README.md", "--verify", "true", "--kind", "impl").returncode, 0)
        self.assertIn("ok next r1 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next r2 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        self.assertEqual(run(self.repo, "plan", "add", "r3", "Review report A", "--deps", "none", "--files", "README.md", "--output", "reports/shared.md", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "r4", "Review report B", "--deps", "none", "--files", "README.md", "--output", "reports/shared.md", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertIn("ok next r3 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)

    def test_readonly_output_changes_invalidate_verification(self):
        self.init()
        (self.repo / "report.md").write_text("reviewed v1")
        self.assertEqual(run(self.repo, "plan", "add", "r", "Review", "--deps", "none", "--files", "README.md", "--output", "report.md", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertIn("ok next r doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "r").stdout)
        (self.repo / "report.md").write_text("reviewed v2")
        stale = run(self.repo, "done", "r")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("VERIFIED ledger", stale.stdout)

    def test_resumed_failure_remains_unresolved_until_terminated(self):
        self.init()
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "a", "--kind", "net", "--record", "error:net;run:host-1").stdout)
        self.assertIn("doing", run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "a", "--kind", "tool", "--record", "error:tool;run:host-1").stdout)
        self.assertIn("doing", run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active").stdout)
        run_dir = self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
        self.assertEqual(sum(event.get("type") == "fail" for event in events), 2)
        self.assertEqual(sum(event.get("type") == "reopen" and event.get("resolution") == "resumed" for event in events), 2)
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        self.assertNotEqual(run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active").returncode, 0)

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

        def claim():
            result = subprocess.run([str(XR), "--repo", str(self.repo), "next"], capture_output=True, text=True, env=env)
            return result.stdout.strip()

        with ThreadPoolExecutor(max_workers=4) as pool:
            claimed = list(pool.map(lambda _: claim(), range(4)))
        doing = [line for line in claimed if " doing" in line]
        self.assertEqual(len(doing), 1)

    def _epoch(self) -> int:
        run_id = (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        text = (self.repo / ".work-docs" / "runs" / run_id / "RUN.md").read_text()
        match = re.search(r"^dispatch_epoch:\s*(\d+)", text, re.M)
        self.assertIsNotNone(match)
        return int(match.group(1))

    def _finish_pair(self) -> None:
        self.assertEqual(run(self.repo, "plan", "add", "u", "U", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "i", "集成", "--deps", "u", "--files", "README.md", "--verify", "true", "--kind", "integration").returncode, 0)
        self.assertIn("ok next u doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "u").stdout)
        self.assertEqual(run(self.repo, "done", "u").returncode, 0)
        self.assertIn("ok next i doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "i").stdout)
        self.assertEqual(run(self.repo, "done", "i").returncode, 0)

    def test_inspect_reports_abandoned_as_not_done(self):
        self.init()
        run(self.repo, "plan", "add", "u", "U", "--deps", "none", "--files", "README.md", "--verify", "true")
        run(self.repo, "next")
        run(self.repo, "verify", "u")
        run(self.repo, "done", "u")
        run(self.repo, "plan", "add", "v", "V", "--deps", "none", "--files", "README.md", "--verify", "true")
        run(self.repo, "next")
        run(self.repo, "fail", "v", "--kind", "cap", "--record", "error:cap;run:r")
        out = json.loads(run(self.repo, "inspect", "--json").stdout)
        self.assertEqual(out["mode"], "managed")
        self.assertFalse(out["done_met"])
        self.assertTrue(any("abandoned" in reason for reason in out["reasons"]))

    def test_inspect_requires_acceptance_source(self):
        self.init()
        run(self.repo, "plan", "add", "u", "U", "--deps", "none", "--files", "README.md", "--verify", "true")
        run(self.repo, "next")
        run(self.repo, "verify", "u")
        run(self.repo, "done", "u")
        (self.repo / "req.md").write_text("需求：只读检查\n")
        bad = run(self.repo, "acceptance", "set", "A1", "只读检查", "--source", "missing.md", "--units", "u")
        self.assertNotEqual(bad.returncode, 0)
        ok = run(self.repo, "acceptance", "set", "A1", "只读检查", "--source", "req.md", "--units", "u")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        out = json.loads(run(self.repo, "inspect", "--json").stdout)
        self.assertFalse(out["done_met"])
        self.assertEqual(out["acceptance_status"]["total"], 1)

    def test_finish_refuses_stale_evidence(self):
        self.init()
        target = self.repo / "README.md"
        self._finish_pair()
        (self.repo / "req.md").write_text("需求：保持不变\n")
        self.assertEqual(run(self.repo, "acceptance", "set", "A1", "保持不变", "--source", "req.md", "--units", "u").returncode, 0)
        self.assertEqual(run(self.repo, "finish").returncode, 0)
        target.write_text("changed\n")
        again = run(self.repo, "finish")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("stale", again.stdout)
        stale = run(self.repo, "done", "u")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("verify", stale.stdout)

    def test_pause_keeps_active_and_resume_needs_confirmation(self):
        run_id = self.init()
        self.assertEqual(run(self.repo, "pause", "--reason", "等待确认", "--record", "session:abc").returncode, 0)
        self.assertTrue((self.repo / ".work-docs" / "runs" / "ACTIVE").exists())
        self.assertIn("phase: paused", (self.repo / ".work-docs" / "runs" / run_id / "RUN.md").read_text())
        self.assertNotEqual(run(self.repo, "resume").returncode, 0)
        self.assertEqual(run(self.repo, "resume", "--confirm", "--record", "user:ok").returncode, 0)

    def test_take_ownership_rewrites_binding(self):
        run_id = self.init()
        (self.repo / ".work-docs" / "runs" / run_id / "binding.json").write_text(json.dumps({
            "schema": 1, "workspace": str(self.repo.resolve()), "run_id": run_id,
            "session_id": "s-old", "owner": "host", "created_at": "2026-10-20T00:00:00+08:00", "lease": "active",
        }))
        self.assertNotEqual(run(self.repo, "resume", "--confirm", "--record", "user:ok").returncode, 0)
        ok = run(self.repo, "resume", "--confirm", "--take-ownership", "--record", "user:ok")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        binding = json.loads((self.repo / ".work-docs" / "runs" / run_id / "binding.json").read_text())
        self.assertNotEqual(binding["session_id"], "s-old")
        self.assertIn("s-old", (self.repo / ".work-docs" / "runs" / run_id / "events.jsonl").read_text())

    def test_acceptance_rebind_is_atomic(self):
        self.init()
        (self.repo / "req.md").write_text("需求：有替代\n")
        run(self.repo, "plan", "add", "u", "U", "--deps", "none", "--files", "README.md", "--verify", "true")
        run(self.repo, "next")
        run(self.repo, "fail", "u", "--kind", "cap", "--record", "error:cap;run:r")
        run(self.repo, "plan", "add", "w", "替代", "--deps", "none", "--files", "README.md", "--verify", "true")
        run(self.repo, "acceptance", "set", "A1", "有替代", "--source", "req.md", "--units", "u")
        self.assertEqual(run(self.repo, "acceptance", "rebind", "A1", "--units", "w").returncode, 0)
        out = json.loads(run(self.repo, "acceptance", "list", "--json").stdout)
        row = next(item for item in out["rows"] if item["id"] == "A1")
        self.assertEqual(row["units"], "w")
        inspected = json.loads(run(self.repo, "inspect", "--json").stdout)
        self.assertFalse(any("abandoned" in reason for reason in inspected["reasons"]))

    def test_finish_vs_dispatch_race(self):
        self.init()
        self._finish_pair()
        (self.repo / "req.md").write_text("需求：竞态\n")
        run(self.repo, "acceptance", "set", "A1", "竞态", "--source", "req.md", "--units", "u")
        epoch0 = self._epoch()
        self.assertEqual(run(self.repo, "done", "u").returncode, 0)
        out = run(self.repo, "finish")
        self.assertGreater(self._epoch(), epoch0)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        (self.repo / "README.md").write_text("touched\n")
        self.assertNotEqual(run(self.repo, "finish").returncode, 0)

    def test_explicit_run_id_does_not_fall_back(self):
        run_id = self.init()
        missing = run(self.repo, "--run-id", "20260101-0000-missing", "status")
        self.assertNotEqual(missing.returncode, 0)
        self.assertNotIn(run_id, missing.stdout)
        escaped = run(self.repo, "--run-id", "../x", "status")
        self.assertNotEqual(escaped.returncode, 0)
        self.assertEqual((self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip(), run_id)

    def test_legacy_inspect_is_readonly(self):
        run_id = self.init()
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        text = (run_dir / "RUN.md").read_text()
        text = re.sub(r"^phase:.*\n", "", text, flags=re.M)
        (run_dir / "RUN.md").write_text(text)
        (run_dir / "binding.json").unlink()
        (run_dir / "acceptance.tsv").unlink()
        inspected = run(self.repo, "inspect", "--json")
        self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
        out = json.loads(inspected.stdout)
        self.assertEqual(out["mode"], "legacy")
        self.assertFalse(out["automation_allowed"])
        self.assertFalse(out["done_met"])


if __name__ == "__main__":
    unittest.main()
