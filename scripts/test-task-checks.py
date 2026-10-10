#!/usr/bin/env python3
"""Task protocol tests. Retain synthetic artifacts for inspection."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/x-rail/scripts'
sys.path.insert(0, str(SCRIPTS))
import task_checks as checks


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='x-rail-task-')).resolve()
        self.task = self.root / '.work-docs/tasks/example'
        self.task.mkdir(parents=True)
        for name in ['evidence', 'audit']:
            (self.task / name).mkdir()
        (self.root / 'input.txt').write_text('input\n')
        self.contract = (ROOT / 'tests/contract-fixtures/valid-low/contract.md').read_text()
        self.contract = self.contract.replace('task_id: fixture-valid-low', 'task_id: example').replace('## Decision Gates', '## Decision Gates\naction_categories: none')
        (self.task / 'contract.md').write_text(self.contract)
        (self.task / 'audit/contract-r1.md').write_text(self.contract)
        self.state = '\n'.join([
            'task_id: example', 'level: L1', 'stage: exec', 'status: done', 'contract_revision: 1',
            'contract_fingerprint: ' + hashlib.sha256(self.contract.encode()).hexdigest(),
            'evidence_schema: 2', 'budget: 59/60', 'calls_since_progress: 0',
            'last_progress_at: 2026-09-28T15:00:00Z',
            'required_verification: A1 status=passed evidence=evidence/check.txt',
            'evidence:check|acceptance=A1|command=manual check|run_at=2026-09-28T15:00:00Z|result=passed|last_edit_at=2026-09-28T15:00:00Z|inputs=evidence/check.inputs.json|contract_revision=1',
        ]) + '\n'
        (self.task / 'state.md').write_text(self.state)
        (self.task / 'evidence/check.txt').write_text('Actual input checked: passed\n')
        self.inputs()

    def inputs(self, files=None):
        data = {'version': 1, 'contract_revision': 1, 'workspace_root': str(self.root),
                'files': files if files is not None else [{'path': 'input.txt', 'state': 'present',
                'sha256': hashlib.sha256((self.root / 'input.txt').read_bytes()).hexdigest()}]}
        (self.task / 'evidence/check.inputs.json').write_text(json.dumps(data))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / 'task.py'), *args], capture_output=True, text=True)

    def assert_bad(self, text=None, reason=None):
        if text is not None:
            (self.task / 'state.md').write_text(text)
        with self.assertRaises(ValueError) as error:
            checks.check_state(self.task)
        if reason:
            self.assertIn(reason, str(error.exception))

    def test_valid_strict_and_candidate(self):
        checks.check_state(self.task)
        (self.task / 'state.md').write_text(self.state.replace('status: done', 'status: in_progress'))
        candidate = self.task / 'candidate.md'
        candidate.write_text(self.state)
        p = self.run_cli('complete', str(self.task), '--candidate', str(candidate))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.task / 'state.md').read_text(), self.state)

    def test_missing_schema_evidence_and_review(self):
        for line in ['evidence_schema: 2\n', next(x for x in self.state.splitlines(True) if x.startswith('evidence:'))]:
            with self.subTest(line=line):
                self.assert_bad(self.state.replace(line, ''))
        c = (self.contract.replace('review_policy: auto', 'review_policy: user-confirm')
             .replace('review: auto', 'review: user-confirm')
             .replace('risk: low', 'risk: medium')
             .replace('confirmation: exempted', 'confirmation: required')
             .replace('confirmation_status: exempted', 'confirmation_status: confirmed')
             .replace('confirmation_reason: 低风险文档任务', 'confirmation_reason: 已确认的本地实施')
             .replace('confirmation_by: system', 'confirmation_by: tester')
             .replace('confirmation_at: 2026-10-05T10:00+08:00', 'confirmation_at: 2026-10-05T10:00:00+08:00')
             .replace('review: user-confirm', 'review: user-confirm\nconfirmation_source: test'))
        (self.task / 'contract.md').write_text(c)
        (self.task / 'audit/contract-r1.md').write_text(c)
        s = self.state.replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
        self.assert_bad(s, 'review evidence')

    def test_time_offsets_and_invalid_dates(self):
        self.assertLess(checks.parse_evidence_time('2026-09-28T20:00:00+08:00'), checks.parse_evidence_time('2026-09-28T15:00:00Z'))
        self.assertEqual(checks.parse_evidence_time('2026-09-28T23:00:00+08:00'), checks.parse_evidence_time('2026-09-28T15:00:00Z'))
        for time in ['2026-02-30T00:00:00Z', '2026-01-01T25:00:00Z', '2026-01-01', '2026-01-01T00:00:00', '2026-01-01T00:00:00+24:00', '2026-01-01 00:00:00Z']:
            with self.subTest(time=time), self.assertRaises(ValueError):
                checks.parse_evidence_time(time)
        self.assert_bad(self.state.replace('run_at=2026-09-28T15:00:00Z', 'run_at=2026-09-28T20:00:00+08:00'), 'stale')

    def test_escape_rejected_before_read(self):
        outside = self.root / 'outside.txt'
        outside.write_text('private')
        (self.task / 'evidence/link.txt').symlink_to(outside)
        from unittest.mock import patch
        original = Path.read_bytes
        reads = []
        def tracked(path):
            reads.append(path.resolve())
            return original(path)
        for path in ['../outside.txt', str(outside), 'evidence/link.txt']:
            with self.subTest(path=path), patch.object(Path, 'read_bytes', tracked):
                self.assert_bad(self.state.replace('evidence=evidence/check.txt', 'evidence=' + path), 'path')
        self.assertNotIn(outside, reads)

    def test_input_changes_and_absence(self):
        (self.root / 'unrelated.txt').write_text('change')
        checks.check_state(self.task)
        (self.root / 'input.txt').write_text('changed')
        self.assert_bad(reason='input')
        self.inputs([{'path': 'removed.txt', 'state': 'absent'}])
        checks.check_state(self.task)
        (self.root / 'removed.txt').write_text('reappeared')
        self.assert_bad(reason='input')

    def test_duplicates(self):
        for extra in ['evidence_schema: 2', 'required_verification: A1 status=failed', next(x for x in self.state.splitlines() if x.startswith('evidence:'))]:
            with self.subTest(extra=extra):
                self.assert_bad(self.state + extra + '\n', 'duplicate')

    def test_command_is_data_and_empty_evidence_rejected(self):
        marker = self.root / 'must-not-exist'
        (self.task / 'state.md').write_text(self.state.replace('command=manual check', 'command=touch ' + str(marker)))
        checks.check_state(self.task)
        self.assertFalse(marker.exists())
        (self.task / 'evidence/check.txt').write_text('')
        self.assert_bad(reason='empty')

    def test_not_run_and_failure_preserves_state(self):
        waiting = self.state.replace('status: done', 'status: in_progress').replace('A1 status=passed evidence=evidence/check.txt', 'A1 status=not_run')
        waiting = '\n'.join(x for x in waiting.splitlines() if not x.startswith('evidence:')) + '\n'
        (self.task / 'state.md').write_text(waiting)
        checks.check_state(self.task)
        candidate = self.task / 'candidate.md'
        candidate.write_text(waiting.replace('status: in_progress', 'status: done'))
        index = self.root / '.work-docs/index.md'
        index.write_text('original index')
        p = self.run_cli('complete', str(self.task), '--candidate', str(candidate))
        self.assertEqual(p.returncode, 1)
        self.assertEqual((self.task / 'state.md').read_text(), waiting)
        self.assertEqual(index.read_text(), 'original index')
        self.assertTrue(candidate.exists())

    def test_snapshot_mutation_and_chain(self):
        (self.task / 'contract.md').write_text(self.contract + '\nchanged\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            checks.check_contract(self.task, mode='locked')
        self.assertEqual((self.task / 'audit/contract-r1.md').read_text(), self.contract)
        (self.task / 'contract.md').write_text(self.contract.replace('contract_revision: 1', 'contract_revision: 2'))
        with self.assertRaisesRegex(ValueError, 'change|snapshot'):
            checks.check_contract(self.task, mode='locked')

    def test_budget_boundaries_and_pause(self):
        checks.check_state(self.task)
        (self.task / 'state.md').write_text(self.state.replace('59/60', '60/60'))
        checks.check_state(self.task)
        self.assert_bad(self.state.replace('59/60', '60/60').replace('status: done', 'status: in_progress'), 'budget')
        self.assert_bad(self.state.replace('59/60', '61/60'), 'budget')
        for status in ['blocked', 'stopped', 'cancelled']:
            (self.task / 'state.md').write_text(self.state.replace('status: done', 'status: ' + status).replace('59/60', '61/60').replace('calls_since_progress: 0', 'calls_since_progress: 20') + 'blocked_by: budget\nunblock_condition: approved budget\nnext_action: preserve artifacts\n')
            checks.check_state(self.task)
        self.assert_bad(self.state.replace('calls_since_progress: 0', 'calls_since_progress: 20').replace('status: done', 'status: in_progress'), 'progress')

    def test_legacy_explicit_and_seal_rejected(self):
        legacy = ROOT / 'tests/contract-fixtures/legacy'
        with self.assertRaises(ValueError):
            checks.check_contract(legacy)
        checks.check_contract(legacy, strict=False)
        p = subprocess.run(['bash', str(SCRIPTS / 'check-contract.sh'), str(legacy), '--seal', '--legacy-readonly'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)

    def test_risk_separate_from_authority(self):
        c = (self.contract.replace('risk: low', 'risk: medium')
             .replace('review_policy: auto', 'review_policy: user-confirm')
             .replace('review: auto', 'review: user-confirm')
             .replace('confirmation: exempted', 'confirmation: required')
             .replace('confirmation_status: exempted', 'confirmation_status: confirmed')
             .replace('confirmation_reason: 低风险文档任务', 'confirmation_reason: 已确认的本地实施')
             .replace('confirmation_by: system', 'confirmation_by: tester')
             .replace('confirmation_at: 2026-10-05T10:00+08:00', 'confirmation_at: 2026-10-05T10:00:00+08:00')
             .replace('review: user-confirm', 'review: user-confirm\nconfirmation_source: test'))
        (self.task / 'contract.md').write_text(c)
        checks.check_contract(self.task)
        exempted = self.contract.replace('risk: low', 'risk: medium').replace('review_policy: auto', 'review_policy: user-confirm').replace('review: auto', 'review: user-confirm')
        (self.task / 'contract.md').write_text(exempted)
        checks.check_contract(self.task)
        pending = (c.replace('action_categories: none', 'action_categories: cost')
                    .replace('confirmation_status: confirmed', 'confirmation_status: pending'))
        (self.task / 'contract.md').write_text(pending)
        checks.check_contract(self.task, mode='draft')
        with self.assertRaisesRegex(ValueError, 'confirmation'):
            checks.check_contract(self.task)

    def test_candidate_and_concurrent_changes(self):
        candidate = self.task / 'candidate.md'
        candidate.write_text(self.state)
        outside = self.root / 'outside.md'
        outside.write_text(self.state)
        self.assertEqual(self.run_cli('complete', str(self.task), '--candidate', str(outside)).returncode, 1)
        import task as cli
        def mutate():
            (self.task / 'state.md').write_text('changed concurrently')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cli.complete(self.task, candidate, before_commit=mutate)
        self.assertEqual((self.task / 'state.md').read_text(), 'changed concurrently')

    def test_multiple_acceptances_and_snapshot_required(self):
        extra = '\n### A2\noutcome: second\nverification: manual\nverification_type: manual\nlayer: static\nrequired: no\nskip_reason: not needed\n'
        c = self.contract.replace('## Unknowns', extra + '\n## Unknowns')
        (self.task / 'contract.md').write_text(c)
        checks.check_contract(self.task)
        (self.task / 'audit/contract-r1.md').write_text(c)
        s = self.state.replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
        (self.task / 'state.md').write_text(s)
        checks.check_state(self.task)
        (self.task / 'audit/contract-r1.md').rename(self.task / 'audit/saved.md')
        self.assert_bad(reason='snapshot')

    def test_strict_requires_contract_and_actions(self):
        (self.task / 'contract.md').rename(self.task / 'saved-contract.md')
        self.assert_bad(reason='contract')
        (self.task / 'saved-contract.md').rename(self.task / 'contract.md')
        (self.task / 'contract.md').write_text(self.contract.replace('action_categories: none\n', ''))
        with self.assertRaisesRegex(ValueError, 'action_categories'):
            checks.check_contract(self.task)

    def test_review_is_fresh_and_bound(self):
        c = self.contract.replace('review_policy: auto', 'review_policy: user-confirm').replace('review: auto', 'review: user-confirm')
        (self.task / 'contract.md').write_text(c)
        (self.task / 'audit/contract-r1.md').write_text(c)
        (self.task / 'evidence/review.md').write_text('Actual review: passed')
        s = self.state.replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
        s += 'review_evidence: review|policy=user-confirm|status=passed|path=evidence/review.md|inputs=evidence/check.inputs.json|contract_revision=1|run_at=2026-09-28T15:00:00Z|last_edit_at=2026-09-28T15:00:00Z\n'
        (self.task / 'state.md').write_text(s)
        checks.check_state(self.task)
        self.assert_bad(s.replace('|run_at=2026-09-28T15:00:00Z|last_edit_at=', '|run_at=2026-09-28T14:00:00Z|last_edit_at='), 'stale')

    def test_dependency_validation(self):
        c = self.contract + '\n## Dependencies\ndependency: child|task_id=missing|required=yes|acceptance=A1\n'
        (self.task / 'contract.md').write_text(c)
        (self.task / 'audit/contract-r1.md').write_text(c)
        s = self.state.replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
        self.assert_bad(s, 'dependency')
        c = c.replace('task_id=missing', 'task_id=../outside')
        (self.task / 'contract.md').write_text(c)
        with self.assertRaisesRegex(ValueError, 'dependency'):
            checks.check_contract(self.task)

    def test_dependency_success_waiting_cycle_and_optional(self):
        child = self.task.parent / 'child'
        import shutil
        shutil.copytree(self.task, child)
        def set_dependency(directory, text):
            c = self.contract.replace('task_id: example', 'task_id: '+directory.name) + '\n## Dependencies\n' + text + '\n'
            (directory / 'contract.md').write_text(c)
            (directory / 'audit/contract-r1.md').write_text(c)
            s = self.state.replace('task_id: example', 'task_id: '+directory.name).replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
            (directory / 'state.md').write_text(s)
        child_contract = self.contract.replace('task_id: example', 'task_id: child')
        (child / 'contract.md').write_text(child_contract)
        (child / 'audit/contract-r1.md').write_text(child_contract)
        child_state = self.state.replace('task_id: example', 'task_id: child').replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(child_contract.encode()).hexdigest())
        (child / 'state.md').write_text(child_state)
        set_dependency(self.task, 'dependency: review|task_id=child|required=yes|acceptance=A1')
        checks.check_state(self.task)
        for status in ['in_progress', 'blocked', 'stopped', 'cancelled']:
            s = child_state.replace('status: done', 'status: '+status)
            if status != 'in_progress':
                s += 'blocked_by: waiting\nunblock_condition: review\nnext_action: preserve\n'
            (child / 'state.md').write_text(s)
            self.assert_bad(reason='dependency')
        (child / 'state.md').write_text(child_state)
        set_dependency(child, 'dependency: parent|task_id=example|required=yes|acceptance=A1')
        self.assert_bad(reason='cycle')
        set_dependency(self.task, 'dependency: reference|task_id=missing|required=no|acceptance=A1|skip_reason=fixed materials sufficient')
        checks.check_state(self.task)

    def test_identity_scale_duplicate_status_and_json_keys(self):
        self.assert_bad(self.state.replace('task_id: example', 'task_id: other'), 'task_id')
        self.assert_bad(self.state.replace('level: L1', 'level: L2'), 'level')
        self.assert_bad(self.state.replace('status=passed evidence=', 'status=failed status=passed evidence='), 'duplicate')
        (self.task / 'state.md').write_text(self.state)
        manifest = self.task / 'evidence/check.inputs.json'
        manifest.write_text(manifest.read_text().replace('"version": 1', '"version": 0, "version": 1'))
        self.assert_bad(reason='duplicate')

    def test_state_symlink_and_concurrent_input_changes(self):
        import task as cli
        formal = self.task / 'state.md'
        formal.rename(self.task / 'original-state.md')
        formal.symlink_to(self.task / 'original-state.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            checks.check_state(self.task)
        other = self.task.parent / 'second'
        import shutil
        shutil.copytree(self.task, other)
        # Keep the original symlink fixture and use a regular candidate task.
        task_dir = self.root / 'candidate-task/example'
        shutil.copytree(self.task, task_dir, symlinks=False)
        candidate = task_dir / 'candidate.md'
        candidate.write_text(self.state)
        original = (task_dir / 'state.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'input changed'):
            cli.complete(task_dir, candidate, before_commit=lambda: (self.root/'input.txt').write_text('changed during commit'))
        self.assertEqual((task_dir/'state.md').read_bytes(), original)
        self.assertTrue(candidate.exists())

    def test_run_references_observations(self):
        reference = {'version':1,'runs':[{'key':'review','provider':'test','run_id':'original-run','task_id':'child','workspace':str(self.root),'observed_status':'unknown','observed_at':'2026-09-28T15:00:00Z','output_reference':None}]}
        (self.task/'audit/runs.json').write_text(json.dumps(reference))
        observed = checks.read_runs(self.task)
        self.assertEqual(observed[0]['run_id'], 'original-run')
        self.assertEqual(observed[0]['observed_status'], 'unknown')
        reference['runs'][0]['observed_status']='completed'
        reference['runs'][0]['output_reference']='outputs/review.md'
        (self.task/'audit/runs.json').write_text(json.dumps(reference))
        self.assertEqual(checks.read_runs(self.task)[0]['run_id'],'original-run')
        self.assertEqual(checks.read_runs(self.task)[0]['observed_status'],'completed')

    def test_run_status_and_dependency_identity(self):
        run = {'key':'review','provider':'test','run_id':'original-run','task_id':'child','workspace':str(self.root),'observed_status':'invented','observed_at':'2026-09-28T15:00:00Z','output_reference':None}
        path = self.task/'audit/runs.json'
        path.write_text(json.dumps({'version':1,'runs':[run]}))
        with self.assertRaisesRegex(ValueError, 'status'):
            checks.read_runs(self.task)
        run['observed_status']='completed'
        path.write_text(json.dumps({'version':1,'runs':[run]}))
        with self.assertRaisesRegex(ValueError, 'dependency'):
            checks.read_runs(self.task, dependencies=[{'key':'review','task_id':'different'}])
        self.assertEqual(checks.read_runs(self.task, dependencies=[{'key':'review','task_id':'child'}])[0]['run_id'], 'original-run')

    def test_deadline_and_paused_reason(self):
        s = self.state.replace('status: done', 'status: in_progress') + 'started_at: 2026-09-28T14:00:00Z\ndeadline_at: 2026-09-28T14:30:00Z\nupdated_at: 2026-09-28T15:00:00Z\n'
        self.assert_bad(s, 'deadline')
        self.assert_bad(self.state.replace('status: done', 'status: stopped'), 'reason')


if __name__ == '__main__':
    unittest.main(verbosity=2)
