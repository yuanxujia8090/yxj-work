#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
XR = ROOT / "skills" / "x-rail" / "scripts" / "xr"


def run(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(XR), "--repo", str(repo), *args], capture_output=True, text=True, env=env)


def parse_json(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    try:
        value = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"invalid JSON output: {result.stdout!r}") from exc
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {value!r}")
    return value


class XrTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"XR_SESSION": "test-session", "PI_SESSION_ID": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "README.md").write_text("seed\n")

    def tearDown(self):
        self.tmp.cleanup()

    def init(self) -> str:
        result = run(self.repo, "init", "demo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.split()[-1]

    def test_init_uses_real_session_and_rejects_existing_active(self):
        env = os.environ.copy()
        env["PI_SESSION_ID"] = "pi-session-123"
        first = run(self.repo, "init", "demo", env=env)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        run_id = first.stdout.split()[-1]
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        try:
            binding = json.loads((run_dir / "binding.json").read_text())
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            self.fail(f"invalid binding.json: {exc}")
        self.assertEqual(binding["session_id"], "pi-session-123")
        second = run(self.repo, "init", "other", env=env)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("active", second.stdout.lower())
        self.assertEqual((self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip(), run_id)

    def test_init_requires_session_or_explicit_offline(self):
        env = {key: value for key, value in os.environ.items() if key not in {"PI_SESSION_ID", "XR_SESSION"}}
        denied = run(self.repo, "init", "demo", env=env)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("session", denied.stdout.lower())
        allowed = run(self.repo, "init", "demo", "--offline", env=env)
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        snapshot = parse_json(run(self.repo, "inspect", "--json", env=env))
        self.assertFalse(snapshot["automation_allowed"])

    def test_concurrent_init_preserves_single_owner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda slug: run(self.repo, "init", slug), ("one", "two")))
        self.assertEqual(sorted(result.returncode for result in results), [0, 2])
        winner = next(result for result in results if result.returncode == 0).stdout.split()[-1]
        base = self.repo / ".work-docs" / "runs"
        self.assertEqual((base / "ACTIVE").read_text().strip(), winner)
        self.assertEqual([path.name for path in base.iterdir() if path.is_dir()], [winner])

    def test_takeover_advances_generation_and_rejects_stale_writer(self):
        run_id = self.init()
        changed = run(self.repo, "resume", "--session", "next-session", "--confirm", "--take-ownership", "--record", "user:handoff")
        self.assertEqual(changed.returncode, 0, changed.stdout + changed.stderr)
        run_dir = self.repo / ".work-docs" / "runs" / run_id
        before = (run_dir / "units.tsv").read_bytes()
        stale = run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true")
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual((run_dir / "units.tsv").read_bytes(), before)
        try:
            binding = json.loads((run_dir / "binding.json").read_text())
            recorded = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(str(exc))
        self.assertEqual(binding["generation"], 2)
        self.assertEqual(recorded[-1]["generation"], 2)
        self.assertEqual(recorded[-1]["session_id"], "next-session")
        env = {**os.environ, "PI_SESSION_ID": "next-session"}
        late = run(self.repo, "--generation", "1", "plan", "add", "b", "B", "--deps", "none", "--files", "README.md", "--verify", "true", env=env)
        self.assertNotEqual(late.returncode, 0)
        self.assertEqual((run_dir / "units.tsv").read_bytes(), before)

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

    def test_dependency_requires_current_verification_evidence(self):
        self.init()
        (self.repo / "a.txt").write_text("v1\n")
        (self.repo / "b.txt").write_text("b\n")
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "a.txt", "--verify", "true").returncode, 0)
        (self.repo / "c.txt").write_text("independent\n")
        self.assertEqual(run(self.repo, "plan", "add", "b", "B", "--deps", "a", "--files", "b.txt", "--verify", "true").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "c", "C", "--deps", "none", "--files", "c.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        (self.repo / "a.txt").write_text("changed after verification\n")
        snapshot = parse_json(run(self.repo, "inspect", "--json"))
        self.assertIn("a", snapshot["stale_units"])
        self.assertIn("ok next c doing", run(self.repo, "next").stdout)
        self.assertIn("ok next none", run(self.repo, "next").stdout)

    def test_transitive_stale_dependency_blocks_descendant(self):
        self.init()
        for name, deps in (("a", "none"), ("b", "a"), ("c", "b")):
            (self.repo / f"{name}.txt").write_text(name)
            self.assertEqual(run(self.repo, "plan", "add", name, name, "--deps", deps, "--files", f"{name}.txt", "--verify", "true").returncode, 0)
        for name in ("a", "b"):
            self.assertIn(f"ok next {name} doing", run(self.repo, "next").stdout)
            self.assertIn("VERIFIED", run(self.repo, "verify", name).stdout)
            self.assertEqual(run(self.repo, "done", name).returncode, 0)
        (self.repo / "a.txt").write_text("changed")
        snapshot = parse_json(run(self.repo, "inspect", "--json"))
        self.assertNotIn("c", snapshot["ready"])
        self.assertIn("b", snapshot["stale_units"])
        self.assertIn("ok next none", run(self.repo, "next").stdout)

    def test_host_events_require_current_generation_and_reconcile_uncertainty(self):
        run_id = self.init()
        record = self.repo / "host-event.json"
        run_dir = self.repo / ".work-docs" / "runs" / run_id

        def append(event_id, kind, **detail):
            record.write_text(json.dumps({"schema": 1, "event_id": event_id, "workspace": str(self.repo.resolve()),
                                          "run_id": run_id, "session_id": "test-session", "generation": 1,
                                          "type": kind, "detail": detail}))
            return run(self.repo, "--run-id", run_id, "event", "--record", str(record))

        intent = append("intent-1", "op_intent", op_id="call-1", tool="bash", readonly=False)
        self.assertEqual(intent.returncode, 0, intent.stdout + intent.stderr)
        before = (run_dir / "events.jsonl").read_bytes()
        duplicate = run(self.repo, "event", "--record", str(record))
        self.assertEqual(duplicate.returncode, 0, duplicate.stdout + duplicate.stderr)
        self.assertEqual((run_dir / "events.jsonl").read_bytes(), before)
        self.assertIn("call-1", parse_json(run(self.repo, "inspect", "--json"))["unresolved_ops"])
        result = append("result-1", "op_result", op_id="call-1", outcome="error")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("call-1", parse_json(run(self.repo, "inspect", "--json"))["unresolved_ops"])
        resolved = run(self.repo, "op", "reconcile", "call-1", "--resolution", "completed", "--record", "local:checked-file")
        self.assertEqual(resolved.returncode, 0, resolved.stdout + resolved.stderr)
        self.assertNotIn("call-1", parse_json(run(self.repo, "inspect", "--json"))["unresolved_ops"])
        denied = run(self.repo, "--generation", "2", "event", "--record", str(record))
        self.assertNotEqual(denied.returncode, 0)

    def host_event(self, run_id, kind, detail, event_id="host-event"):
        try:
            binding = json.loads((self.repo / ".work-docs/runs" / run_id / "binding.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(f"invalid fixture binding: {exc}")
        record = self.repo / "host-record.json"
        record.write_text(json.dumps({"schema": 1, "event_id": event_id, "workspace": str(self.repo.resolve()),
                                      "run_id": run_id, "session_id": binding["session_id"], "generation": binding["generation"],
                                      "type": kind, "detail": detail}))
        return run(self.repo, "event", "--record", str(record))

    def test_unknown_tool_blocks_claim_and_done(self):
        run_id = self.init()
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        run(self.repo, "next")
        run(self.repo, "verify", "a")
        self.assertEqual(self.host_event(run_id, "op_intent", {"op_id": "call-a", "tool": "bash", "readonly": False}).returncode, 0)
        self.assertNotEqual(run(self.repo, "done", "a").returncode, 0)
        self.assertIn("ok next none", run(self.repo, "next").stdout)
        snapshot = parse_json(run(self.repo, "inspect", "--json"))
        self.assertFalse(snapshot["automation_allowed"])

    def test_worker_receipt_needs_terminal_identity_and_is_idempotent(self):
        run_id = self.init()
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "README.md", "--verify", "true").returncode, 0)
        run(self.repo, "next")
        status_path = self.repo / "worker-status.json"
        session_file = self.repo / "child-session.jsonl"
        session_file.write_text(json.dumps({"type": "session", "id": "child-session"}) + "\n")
        started = self.host_event(run_id, "worker_started", {"op_id": "launch-a", "unit": "a", "child_run_id": "child-a",
                                  "status_path": str(status_path), "launch_digest": "contract-a"})
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        pending = parse_json(run(self.repo, "inspect", "--json"))
        self.assertEqual(pending["pending_workers"], ["child-a"])
        self.assertNotEqual(run(self.repo, "verify", "a").returncode, 0)
        status = {"runId": "child-a", "toolCallId": "launch-a", "launchContractDigest": "contract-a", "state": "running",
                  "processTerminal": {"state": "unknown"}, "steps": [{"status": "complete", "exitCode": 0, "sessionFile": str(session_file)}]}
        status_path.write_text(json.dumps(status))
        self.assertNotEqual(run(self.repo, "receive", "a", "--receipt", str(status_path), "--record", "host:notice").returncode, 0)
        status.update(state="complete", processTerminal={"state": "observed", "runId": "child-a", "instances": [{"exitCode": 0, "signal": None}]})
        status["toolCallId"] = "wrong-launch"
        status_path.write_text(json.dumps(status))
        self.assertNotEqual(run(self.repo, "receive", "a", "--receipt", str(status_path), "--record", "host:notice").returncode, 0)
        status["toolCallId"] = "launch-a"
        status_path.write_text(json.dumps(status))
        accepted = run(self.repo, "receive", "a", "--receipt", str(status_path), "--record", "host:notice")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        run_dir = self.repo / ".work-docs/runs" / run_id
        before = (run_dir / "events.jsonl").read_bytes()
        duplicate = run(self.repo, "receive", "a", "--receipt", str(status_path), "--record", "host:notice")
        self.assertEqual(duplicate.returncode, 0, duplicate.stdout + duplicate.stderr)
        self.assertEqual((run_dir / "events.jsonl").read_bytes(), before)
        snapshot = parse_json(run(self.repo, "inspect", "--json"))
        self.assertEqual(snapshot["pending_workers"], [])
        self.assertFalse(snapshot["done_met"])
        received = list(run_dir.glob("notes/received-*.json"))
        self.assertEqual(len(received), 1)
        try:
            receipt = json.loads(received[0].read_text())
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(f"invalid receipt: {exc}")
        self.assertEqual(receipt["child_sessions"], ["child-session"])
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        status["state"] = "failed"
        status_path.write_text(json.dumps(status))
        self.assertEqual(parse_json(run(self.repo, "inspect", "--json"))["pending_workers"], ["child-a"])
        self.assertNotEqual(run(self.repo, "done", "a").returncode, 0)

    def test_human_evidence_scopes_immutable_reports_and_independent_review(self):
        run_id = self.init()
        source = self.repo / "report.md"
        source.write_text("观察报告 v1\n")
        self.assertEqual(run(self.repo, "plan", "add", "observe", "观察", "--deps", "none", "--files", "report.md", "--verify-kind", "observation").returncode, 0)
        self.assertEqual(run(self.repo, "next").returncode, 0)
        empty = self.repo / "empty.md"
        empty.write_text(" \n")
        self.assertNotEqual(run(self.repo, "evidence", "record", "observe", "--kind", "observation", "--report", str(empty), "--record", "host:observe").returncode, 0)
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "report.md"
            outside.write_text("outside\n")
            self.assertNotEqual(run(self.repo, "evidence", "record", "observe", "--kind", "observation", "--report", str(outside), "--record", "host:observe").returncode, 0)
        self.assertNotEqual(run(self.repo, "evidence", "record", "observe", "--kind", "observation", "--report", str(self.repo / ".work-docs/runs" / run_id / "RUN.md"), "--record", "host:observe").returncode, 0)
        observation = run(self.repo, "evidence", "record", "observe", "--kind", "observation", "--report", str(source), "--record", "host:observe")
        self.assertEqual(observation.returncode, 0, observation.stdout + observation.stderr)
        evidence_dir = self.repo / ".work-docs/runs" / run_id / "notes"
        saved = list(evidence_dir.glob("evidence-observe-observation-*.md"))
        self.assertEqual(len(saved), 1)
        duplicate = run(self.repo, "evidence", "record", "observe", "--kind", "observation", "--report", str(source), "--record", "host:observe")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertEqual(len(list(evidence_dir.glob("evidence-observe-observation-*.md"))), 1)
        (self.repo / "req.md").write_text("需求：观察及独立审查\n")
        self.assertEqual(run(self.repo, "acceptance", "set", "A1", "观察报告有效", "--source", "req.md", "--units", "observe").returncode, 0)
        self.assertEqual(run(self.repo, "done", "observe").returncode, 0)
        self.assertEqual(run(self.repo, "plan", "add", "review", "独立审查", "--deps", "none", "--files", "README.md", "--kind", "review", "--verify-kind", "review").returncode, 0)
        self.assertEqual(run(self.repo, "next").returncode, 0)
        review_report = self.repo / "review.md"
        review_report.write_text("reviewed current inputs\n")
        self.assertNotEqual(run(self.repo, "evidence", "record", "review", "--kind", "review", "--report", str(review_report), "--record", "host:self-review").returncode, 0)
        reviewer = self.repo / "review-session.jsonl"
        review_report.write_text("reviewer-session")
        reviewer.write_text(json.dumps({"type": "session", "id": "reviewer-session", "cwd": str(self.repo.resolve())}) + "\n" +
                            json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": review_report.read_text()}]}}) + "\n")
        accepted = run(self.repo, "evidence", "record", "review", "--kind", "review", "--report", str(review_report), "--inputs", "README.md", "--observer", str(reviewer), "--record", "host:independent-review")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(run(self.repo, "done", "review").returncode, 0)
        inspected = parse_json(run(self.repo, "inspect", "--json"))
        self.assertFalse(inspected["done_met"])
        (self.repo / "README.md").write_text("final input changed\n")
        stale = parse_json(run(self.repo, "inspect", "--json"))
        self.assertIn("review", stale["stale_units"])
        self.assertTrue(any("独立审查" in reason or "stale:review" in reason for reason in stale["reasons"]))
        # 过期后重新取证：旧记录保留，新证据必须绑定新输入。
        review_report.write_text("reviewer-session")
        again = run(self.repo, "evidence", "record", "review", "--kind", "review", "--report", str(review_report), "--inputs", "README.md", "--observer", str(reviewer), "--record", "host:re-review")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(len(list(evidence_dir.glob("evidence-review-review-*.md"))), 2)
        self.assertEqual(len(list(evidence_dir.glob("review-session-review-*.jsonl"))), 2)
        refreshed = parse_json(run(self.repo, "inspect", "--json"))
        self.assertNotIn("review", refreshed["stale_units"])
        self.assertFalse(any("独立审查" in reason for reason in refreshed["reasons"]))

    def test_review_evidence_must_come_from_reviewer_output(self):
        self.init()
        self.assertEqual(run(self.repo, "plan", "add", "review", "独立审查", "--deps", "none", "--files", "README.md", "--kind", "review", "--verify-kind", "review").returncode, 0)
        self.assertEqual(run(self.repo, "next").returncode, 0)
        report = self.repo / "review.md"
        report.write_text("claimed clean")
        reviewer = self.repo / "review-session.jsonl"
        session = {"type": "session", "id": "other-session", "cwd": str(self.repo.resolve())}
        caller = {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "claimed clean"}]}}
        reviewer.write_text(json.dumps(session) + "\n" + json.dumps(caller) + "\n")
        self.assertNotEqual(run(self.repo, "evidence", "record", "review", "--kind", "review", "--report", str(report), "--observer", str(reviewer), "--record", "host:echo").returncode, 0)
        self.assertNotEqual(run(self.repo, "evidence", "record", "review", "--kind", "review", "--report", str(report), "--observer", str(self.repo / "missing.jsonl"), "--record", "host:missing").returncode, 0)
        self.assertNotEqual(run(self.repo, "verify", "review").returncode, 0)
        self.assertIn("review", parse_json(run(self.repo, "inspect", "--json"))["doing"])

    def test_review_required_blocks_finish_without_independent_review(self):
        run_id = self.init()
        self._finish_pair()
        (self.repo / "req.md").write_text("需求：审查门\n")
        run(self.repo, "acceptance", "set", "A1", "有审查", "--source", "req.md", "--units", "i")
        run_dir = self.repo / ".work-docs/runs" / run_id
        (run_dir / "RUN.md").write_text((run_dir / "RUN.md").read_text().replace("review_required: false", "review_required: true"))
        inspected = parse_json(run(self.repo, "inspect", "--json"))
        self.assertFalse(inspected["done_met"])
        self.assertIn("缺少独立审查", inspected["reasons"])
        self.assertNotEqual(run(self.repo, "finish").returncode, 0)

    def test_session_acceptance_source_requires_saved_evidence(self):
        run_id = self.init()
        self._finish_pair()
        (self.repo / "req.md").write_text("需求：会话来源\n")
        self.assertEqual(run(self.repo, "acceptance", "set", "A1", "会话来源", "--source",
                             "session:reviewer-session#entry:e1", "--units", "i").returncode, 0)
        run_dir = self.repo / ".work-docs/runs" / run_id
        # 只有格式，没有审查会话副本：不算覆盖。
        before = parse_json(run(self.repo, "inspect", "--json"))
        self.assertFalse(before["done_met"])
        self.assertTrue(any("session" in reason for reason in before["reasons"]), before["reasons"])
        # 造一份真实审查证据后，同一来源才算覆盖。
        self.assertEqual(run(self.repo, "plan", "add", "r", "审查", "--deps", "i", "--files", "req.md",
                             "--kind", "review", "--verify-kind", "review").returncode, 0)
        run(self.repo, "next")
        report = self.repo / "review.md"
        report.write_text("reviewer-session")
        reviewer = self.repo / "review-session.jsonl"
        reviewer.write_text(json.dumps({"type": "session", "id": "reviewer-session", "cwd": str(self.repo.resolve())}) + "\n" +
                            json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "reviewer-session"}]}}) + "\n")
        self.assertEqual(run(self.repo, "evidence", "record", "r", "--kind", "review", "--report", str(report),
                             "--observer", str(reviewer), "--record", "host:independent-review").returncode, 0)
        after = parse_json(run(self.repo, "inspect", "--json"))
        self.assertFalse(any("session" in reason for reason in after["reasons"]), after["reasons"])

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

    def test_verification_reports_are_immutable_per_attempt(self):
        self.init()
        (self.repo / "input.txt").write_text("v1\n")
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "input.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        first = run(self.repo, "verify", "a")
        self.assertIn("VERIFIED", first.stdout)
        (self.repo / "input.txt").write_text("v2\n")
        second = run(self.repo, "verify", "a")
        self.assertIn("VERIFIED", second.stdout)
        run_dir = self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        with (run_dir / "ledger.tsv").open() as ledger:
            rows = list(csv.DictReader(ledger, delimiter="\t"))
        reports = [row["evidence_path"] for row in rows if row["unit"] == "a"]
        self.assertEqual(len(reports), 2)
        self.assertNotEqual(reports[0], reports[1])
        self.assertTrue(all((run_dir / report).is_file() for report in reports))

    def test_tampered_verification_report_cannot_finish(self):
        self.init()
        (self.repo / "input.txt").write_text("v1\n")
        self.assertEqual(run(self.repo, "plan", "add", "a", "A", "--deps", "none", "--files", "input.txt", "--verify", "true").returncode, 0)
        self.assertIn("ok next a doing", run(self.repo, "next").stdout)
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        run_dir = self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        report = next(run_dir.glob("notes/verify-a-attempt-*.log"))
        report.write_text("tampered\n")
        done = run(self.repo, "done", "a")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("VERIFIED ledger", done.stdout)
        rechecked = run(self.repo, "verify", "a")
        self.assertIn("VERIFIED", rechecked.stdout)
        self.assertNotIn("cached", rechecked.stdout)
        self.assertEqual(report.read_text(), "tampered\n")
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)

    def test_corrupt_event_tail_blocks_inspect(self):
        self.init()
        run_dir = self.repo / ".work-docs" / "runs" / (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        with (run_dir / "events.jsonl").open("a") as events:
            events.write("{broken\n")
        inspected = run(self.repo, "inspect", "--json")
        self.assertEqual(inspected.returncode, 0)
        out = parse_json(inspected)
        self.assertFalse(out["done_met"])
        self.assertIn("事件日志损坏", out["reasons"])

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
        self.assertEqual(run(self.repo, "close").returncode, 0)
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
        # Reader and total limits currently match (5/5); reader-only rejection is not independently distinguishable.
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

    def test_resuming_reader_uses_available_reader_capacity(self):
        self.init()
        for name in ("r1", "r2", "r3", "r4", "r5"):
            self.assertEqual(run(self.repo, "plan", "add", name, name, "--deps", "none", "--files", f"{name}.txt", "--verify", "true", "--kind", "review").returncode, 0)
        self.assertIn("ok next r1 doing", run(self.repo, "next").stdout)
        self.assertIn("blocked", run(self.repo, "fail", "r1", "--kind", "net", "--record", "run:r1").stdout)
        for name in ("r2", "r3", "r4"):
            self.assertIn(f"ok next {name} doing", run(self.repo, "next").stdout)
        resumed = run(self.repo, "reopen", "r1", "--resolution", "resumed", "--record", "host:still-active")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertIn("ok next r5 doing", run(self.repo, "next").stdout)
        self.assertIn("ok next none concurrency", run(self.repo, "next").stdout)

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
        try:
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            self.fail(f"invalid events.jsonl: {exc}")
        self.assertEqual(sum(event.get("type") == "fail" for event in events), 2)
        self.assertEqual(sum(event.get("type") == "reopen" and event.get("resolution") == "resumed" for event in events), 2)
        self.assertIn("VERIFIED", run(self.repo, "verify", "a").stdout)
        self.assertEqual(run(self.repo, "done", "a").returncode, 0)
        self.assertNotEqual(run(self.repo, "reopen", "a", "--resolution", "resumed", "--record", "host:still-active").returncode, 0)

    def test_model_breaker_does_not_change_task_concurrency(self):
        def setup_repo() -> Path:
            repo = Path(tempfile.mkdtemp())
            (repo / "README.md").write_text("seed\n")
            self.assertEqual(run(repo, "init", "demo").returncode, 0)
            for name in ("a", "b", "c", "d", "e"):
                path = f"f-{name}.txt"
                (repo / path).write_text(name)
                result = run(repo, "plan", "add", name, name, "--deps", "none", "--files", path, "--verify", "true")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return repo

        baseline_repo = setup_repo()
        guarded_repo = setup_repo()
        state = guarded_repo / "breaker.json"
        state.write_text(json.dumps({"version": 1, "disabled": False, "breakers": {"openai26/gpt-6.1-sol": {"open": True}}, "runs": {}}))
        env = os.environ.copy()
        env["X_FAILOVER_STATE"] = str(state)
        baseline = [run(baseline_repo, "next").stdout.strip() for _ in range(6)]
        guarded = [run(guarded_repo, "next", env=env).stdout.strip() for _ in range(6)]
        self.assertEqual(baseline, guarded)
        self.assertEqual(sum(line.endswith(" doing") for line in baseline), 2)

    def _epoch(self) -> int:
        run_id = (self.repo / ".work-docs" / "runs" / "ACTIVE").read_text().strip()
        text = (self.repo / ".work-docs" / "runs" / run_id / "RUN.md").read_text()
        match = re.search(r"^dispatch_epoch:\s*(\d+)", text, re.M)
        if match is None:
            self.fail("RUN.md missing dispatch_epoch")
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
        out = parse_json(run(self.repo, "inspect", "--json"))
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
        out = parse_json(run(self.repo, "inspect", "--json"))
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
        inspected = parse_json(run(self.repo, "inspect", "--json"))
        self.assertEqual(inspected["receipt_status"], "stale")

    def test_finish_receipt_is_authoritative_and_detects_corruption(self):
        self.init()
        self._finish_pair()
        (self.repo / "req.md").write_text("需求：收据有效性\n")
        run(self.repo, "acceptance", "set", "A1", "收据有效性", "--source", "req.md", "--units", "u")
        self.assertEqual(run(self.repo, "finish").returncode, 0)
        valid = parse_json(run(self.repo, "inspect", "--json"))
        self.assertEqual(valid["receipt_status"], "valid")
        self.assertTrue(valid["done_met"])
        run_dir = self.repo / ".work-docs/runs" / (self.repo / ".work-docs/runs/ACTIVE").read_text().strip()
        (run_dir / "finish.json").write_text("{broken")
        invalid = parse_json(run(self.repo, "inspect", "--json"))
        self.assertEqual(invalid["receipt_status"], "invalid")
        self.assertFalse(invalid["done_met"])
        self.assertIn("receipt:invalid", invalid["reasons"])

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
        try:
            binding = json.loads((self.repo / ".work-docs" / "runs" / run_id / "binding.json").read_text())
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            self.fail(f"invalid binding.json: {exc}")
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
        out = parse_json(run(self.repo, "acceptance", "list", "--json"))
        row = next(item for item in out["rows"] if item["id"] == "A1")
        self.assertEqual(row["units"], "w")
        inspected = parse_json(run(self.repo, "inspect", "--json"))
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
        out = parse_json(inspected)
        self.assertEqual(out["mode"], "legacy")
        self.assertFalse(out["automation_allowed"])
        self.assertFalse(out["done_met"])


if __name__ == "__main__":
    unittest.main()
