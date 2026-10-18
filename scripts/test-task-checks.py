#!/usr/bin/env python3
# pyright: reportMissingImports=false
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

    def fresh_task(self):
        directory = self.root / '.work-docs/tasks/new-task'
        directory.mkdir()
        contract = self.contract.replace('task_id: example', 'task_id: new-task').replace('verification_type: manual', 'verification_type: automatic')
        (directory / 'contract.md').write_text(contract)
        return directory

    def test_start_generates_checked_state_and_refuses_existing_state(self):
        directory = self.fresh_task()
        p = self.run_cli('start', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        fields = checks.check_state(directory)
        self.assertEqual(fields['status'], 'in_progress')
        self.assertEqual(fields['budget'], 'untracked/60')
        self.assertIn('A1 status=not_run', (directory / 'state.md').read_text())
        original = (directory / 'state.md').read_bytes()
        p = self.run_cli('start', str(directory))
        self.assertEqual(p.returncode, 1)
        self.assertEqual((directory / 'state.md').read_bytes(), original)

    def run_verification(self, directory, command, expect='actual result', evidence='actual', *extra):
        return self.run_cli('run', str(directory), '--acceptance', 'A1', '--evidence', evidence,
                            '--workspace', str(self.root), '--input', 'input.txt', '--expect', expect,
                            '--command', command, *extra)

    def test_run_and_finish_bind_actual_command_output(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        p = self.run_verification(directory, "printf 'actual result\\n'")
        self.assertEqual(p.returncode, 0, p.stderr)
        checks.check_state(directory)
        self.assertIn('actual result', (directory / 'evidence/actual.txt').read_text())
        manifest = json.loads((directory / 'evidence/actual.inputs.json').read_text())
        self.assertEqual(manifest['files'][0]['sha256'], hashlib.sha256((self.root / 'input.txt').read_bytes()).hexdigest())
        index = self.root / '.work-docs/index.md'
        index.write_text('| new-task | run | in_progress |\n')
        p = self.run_cli('finish', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['status'], 'done')
        self.assertIn('| done |', index.read_text())

    def test_finish_does_not_require_or_trust_manual_tool_count(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'").returncode, 0)
        p = self.run_cli('finish', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['status'], 'done')
        self.assertIn('budget: untracked/', (directory / 'state.md').read_text())

    def test_optional_used_is_metadata_only(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'").returncode, 0)
        p = self.run_cli('finish', str(directory), '--used', '999999')
        self.assertEqual(p.returncode, 0, p.stderr)
        state = (directory / 'state.md').read_text()
        self.assertIn('tool_count_note: 999999', state)
        self.assertIn('budget: untracked/', state)

    def test_run_requires_declared_input(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        p = self.run_cli('run', str(directory), '--acceptance', 'A1', '--evidence', 'no-input',
                         '--workspace', str(self.root), '--expect', 'actual result',
                         '--command', "printf 'actual result\\n'")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('input', p.stderr.lower())

    def test_run_failed_output_does_not_pass_acceptance(self):
        for command, expected in [("printf 'different result'", 'actual result'), ("printf 'actual result'; exit 2", 'actual result')]:
            directory = self.fresh_task()
            self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
            p = self.run_verification(directory, command, expected)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn('A1 status=failed', (directory / 'state.md').read_text())
            original = (directory / 'state.md').read_bytes()
            p = self.run_cli('finish', str(directory), '--used', '2')
            self.assertEqual(p.returncode, 1)
            self.assertEqual((directory / 'state.md').read_bytes(), original)
            directory.rename(directory.with_name('failed-'+str(len(list(directory.parent.iterdir())))))

    def test_run_changed_input_and_finish_stale_evidence_preserve_state(self):
        directory = self.fresh_task()
        self.run_cli('start', str(directory))
        original = (directory / 'state.md').read_bytes()
        p = self.run_verification(directory, "printf 'changed' > input.txt; printf 'actual result'")
        self.assertEqual(p.returncode, 1)
        self.assertIn('input changed', p.stderr)
        self.assertEqual((directory / 'state.md').read_bytes(), original)
        p = self.run_verification(directory, "printf 'actual result'", evidence='second')
        self.assertEqual(p.returncode, 0, p.stderr)
        original = (directory / 'state.md').read_bytes()
        (self.root / 'input.txt').write_text('changed after verification')
        p = self.run_cli('finish', str(directory), '--used', '2')
        self.assertEqual(p.returncode, 1)
        self.assertIn('input changed', p.stderr)
        self.assertEqual((directory / 'state.md').read_bytes(), original)

    def test_run_rejects_manual_and_escaping_paths_before_execution(self):
        directory = self.fresh_task()
        contract = (directory / 'contract.md').read_text().replace('verification_type: automatic', 'verification_type: manual')
        (directory / 'contract.md').write_text(contract)
        self.run_cli('start', str(directory))
        p = self.run_verification(directory, 'touch must-not-run; printf "actual result"')
        self.assertEqual(p.returncode, 1)
        self.assertIn('automatic', p.stderr)
        self.assertFalse((self.root / 'must-not-run').exists())
        directory.rename(directory.with_name('manual-task'))
        directory = self.fresh_task()
        self.run_cli('start', str(directory))
        for extra in [('--input', '../outside.txt'), ('--input', str(self.root / 'input.txt')),
                      ('--input', '.work-docs/tasks/new-task/state.md')]:
            p = self.run_verification(directory, 'touch must-not-run', 'x', 'unsafe', *extra)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertFalse((self.root / 'must-not-run').exists())
        outside = self.root / 'outside-evidence'
        outside.mkdir()
        (directory / 'evidence').symlink_to(outside)
        p = self.run_verification(directory, 'touch must-not-run', 'x')
        self.assertEqual(p.returncode, 1)
        self.assertFalse((self.root / 'must-not-run').exists())

    def test_run_pipeline_failure_timeout_and_budget(self):
        directory = self.fresh_task()
        self.run_cli('start', str(directory))
        for name, command, extra in [
            ('pipeline', "false | printf 'actual result'", ()),
            ('timeout', "printf 'actual result'; sleep 5", ('--timeout', '0.05')),
        ]:
            p = self.run_verification(directory, command, 'actual result', name, *extra)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn('A1 status=failed', (directory / 'state.md').read_text())
        p = self.run_verification(directory, 'touch optional-count-marker; printf x', 'x', 'optional-count', '--used', '999999')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((self.root / 'optional-count-marker').exists())

    def test_run_does_not_overwrite_receipt_and_quotes_pipe_command(self):
        directory = self.fresh_task()
        self.run_cli('start', str(directory))
        p = self.run_verification(directory, "printf 'actual result' | cat")
        self.assertEqual(p.returncode, 0, p.stderr)
        checks.check_state(directory)
        receipt = (directory / 'evidence/actual.txt').read_bytes()
        p = self.run_verification(directory, 'touch must-not-run')
        self.assertEqual(p.returncode, 1)
        self.assertEqual((directory / 'evidence/actual.txt').read_bytes(), receipt)
        self.assertFalse((self.root / 'must-not-run').exists())

    def pending_manual(self, policy='auto'):
        directory = self.fresh_task()
        contract = (directory / 'contract.md').read_text().replace('verification_type: automatic', 'verification_type: manual')
        if policy != 'auto':
            contract = contract.replace('review_policy: auto', 'review_policy: '+policy).replace('review: auto', 'review: '+policy)
        (directory / 'contract.md').write_text(contract)
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        return directory

    def capture(self, directory, name='observation'):
        p = self.run_cli('capture', str(directory), '--evidence', name,
                         '--workspace', str(self.root), '--input', 'input.txt')
        self.assertEqual(p.returncode, 0, p.stderr)
        return 'evidence/'+name+'.inputs.json'

    def record_manual(self, directory, inputs, name='observed', result='passed', *extra):
        import task as cli
        report = directory / 'evidence' / (name+'.md')
        report.write_text('Observed the requested behavior on input.txt; result='+result)
        return self.run_cli('record', str(directory), '--acceptance', 'A1', '--evidence', name,
                            '--report', 'evidence/'+name+'.md', '--inputs', inputs,
                            '--observed-at', cli.now(), '--result', result,
                            '--observation', 'Read input.txt and checked the requested behavior', *extra)

    def test_update_pause_resume_preserves_evidence_and_progress_time(self):
        directory = self.pending_manual()
        original = checks.check_state(directory)
        p = self.run_cli('update', str(directory), '--stage', 'review', '--next-action', 'inspect behavior')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['last_progress_at'], original['last_progress_at'])
        p = self.run_cli('update', str(directory), '--status', 'blocked', '--blocked-by', 'service unavailable',
                         '--unblock-condition', 'service responds', '--next-action', 'check original service')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['status'], 'blocked')
        p = self.run_cli('update', str(directory), '--status', 'in_progress', '--reason', 'service responds', '--next-action', 'inspect behavior')
        self.assertEqual(p.returncode, 0, p.stderr)
        fields = checks.check_state(directory)
        self.assertEqual(fields['blocked_by'], 'none')
        self.assertEqual(fields['unblock_condition'], 'none')
        self.assertEqual(fields['last_progress_at'], original['last_progress_at'])
        self.assertIn('service responds', (directory / 'state.md').read_text())
        inputs = self.capture(directory)
        self.assertEqual(self.record_manual(directory, inputs).returncode, 0)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)

    def test_update_rejects_unsafe_transitions_and_fields_without_writes(self):
        directory = self.pending_manual()
        before = (directory / 'state.md').read_bytes()
        for extra in [('--status', 'done'), ('--status', 'blocked'), ('--stage', 'invented'),
                      ('--next-action', 'bad\nstatus: done'), ('--status', 'in_progress'),
                      ('--contract-revision', '2')]:
            p = self.run_cli('update', str(directory), *extra)
            self.assertNotEqual(p.returncode, 0, p.stderr)
            self.assertEqual((directory / 'state.md').read_bytes(), before)
        p = self.run_cli('update', str(self.task), '--next-action', 'reopen')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.task / 'state.md').read_text(), self.state)

    def test_summary_reuses_evidence_and_reports_stale_without_writes(self):
        inputs = self.task / 'evidence/check.inputs.json'
        before = {p: p.read_bytes() for p in self.task.rglob('*') if p.is_file()}
        p = self.run_cli('summary', str(self.task))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('A1: passed', p.stdout)
        self.assertIn('evidence/check.txt', p.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in self.task.rglob('*') if p.is_file()})
        (self.root / 'unrelated.txt').write_text('unrelated change')
        self.assertIn('A1: passed', self.run_cli('summary', str(self.task)).stdout)
        (self.root / 'input.txt').write_text('changed behavior')
        p = self.run_cli('summary', str(self.task))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('A1: stale', p.stdout)
        self.assertIn('input changed', p.stdout)
        self.assertNotIn('A1: passed', p.stdout)
        self.assertEqual(inputs.read_bytes(), before[inputs])
        self.assertEqual((self.task / 'state.md').read_bytes(), before[self.task/'state.md'])

    def test_stale_evidence_can_be_paused_and_replaced(self):
        directory = self.pending_manual()
        inputs = self.capture(directory)
        self.assertEqual(self.record_manual(directory, inputs).returncode, 0)
        (self.root / 'input.txt').write_text('new input')
        p = self.run_cli('update', str(directory), '--status', 'blocked', '--blocked-by', 'input changed',
                         '--unblock-condition', 'recheck current input', '--next-action', 'capture current input')
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.run_cli('update', str(directory), '--status', 'in_progress', '--reason', 'ready to recheck', '--next-action', 'capture')
        self.assertEqual(p.returncode, 0, p.stderr)
        inputs = self.capture(directory, 'current')
        self.assertEqual(self.record_manual(directory, inputs, 'current-result').returncode, 0)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)
        self.assertIn('evidence:observed|', (directory / 'state.md').read_text())

    def test_record_requires_original_bound_observation_and_preserves_time(self):
        import task as cli
        directory = self.pending_manual()
        inputs = self.capture(directory)
        manifest = json.loads((directory / inputs).read_text())
        self.assertIn('captured_at', manifest)
        observed_at = cli.now()
        report = directory / 'evidence/report.md'
        report.write_text('Actual observed result')
        p = self.run_cli('record', str(directory), '--acceptance', 'A1', '--evidence', 'manual',
                         '--report', 'evidence/report.md', '--inputs', inputs, '--observed-at', observed_at,
                         '--result', 'passed', '--observation', 'Read input.txt')
        self.assertEqual(p.returncode, 0, p.stderr)
        state = (directory / 'state.md').read_text()
        self.assertIn('|run_at='+observed_at+'|', state)
        self.assertIn('|recorded_at=', state)
        self.assertEqual(report.read_text(), 'Actual observed result')
        p = self.run_cli('summary', str(directory))
        self.assertIn('evidence/report.md', p.stdout)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)

    def test_record_rejects_stale_future_missing_and_automatic_without_state_change(self):
        import task as cli
        directory = self.pending_manual()
        inputs = self.capture(directory)
        report = directory/'evidence/report.md'
        report.write_text('Actual result')
        before = (directory/'state.md').read_bytes()
        base = ['record', str(directory), '--acceptance', 'A1', '--evidence', 'invalid',
                '--report', 'evidence/report.md', '--inputs', inputs, '--result', 'passed', '--observation', 'checked']
        for observed in ['2000-01-01T00:00:00Z', '2099-01-01T00:00:00Z']:
            p = self.run_cli(*base, '--observed-at', observed)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual((directory/'state.md').read_bytes(), before)
        (self.root/'input.txt').write_text('changed')
        p = self.run_cli(*base, '--observed-at', cli.now())
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('input changed', p.stderr)
        self.assertEqual((directory/'state.md').read_bytes(), before)
        directory.rename(directory.with_name('manual-pending'))
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        inputs = self.capture(directory)
        p = self.record_manual(directory, inputs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('non-automatic', p.stderr)

    def test_failed_observation_cannot_finish_and_review_needs_provenance(self):
        directory = self.pending_manual('user-confirm')
        inputs = self.capture(directory)
        self.assertEqual(self.record_manual(directory, inputs, 'failure', 'failed').returncode, 0)
        self.assertNotEqual(self.run_cli('finish', str(directory)).returncode, 0)
        self.assertEqual(self.record_manual(directory, inputs, 'success').returncode, 0)
        import task as cli
        report = directory/'evidence/review.md'
        report.write_text('Independent report artifact, synthetic test')
        base = ['record', str(directory), '--review', '--evidence', 'review', '--report', 'evidence/review.md',
                '--inputs', inputs, '--observed-at', cli.now(), '--result', 'passed', '--observation', 'Independent review']
        before = (directory/'state.md').read_bytes()
        p = self.run_cli(*base)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((directory/'state.md').read_bytes(), before)
        p = self.run_cli(*base, '--reviewer', 'synthetic independent reviewer', '--source', 'synthetic-run-1')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('reviewer=synthetic independent reviewer', (directory/'state.md').read_text())
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)

    def test_capture_refuses_overwrite_and_paths(self):
        directory = self.pending_manual()
        inputs = self.capture(directory)
        original = (directory/inputs).read_bytes()
        p = self.run_cli('capture', str(directory), '--evidence', 'observation', '--workspace', str(self.root), '--input', 'input.txt')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((directory/inputs).read_bytes(), original)
        p = self.run_cli('capture', str(directory), '--evidence', 'escape', '--workspace', str(self.root), '--input', '../outside')
        self.assertNotEqual(p.returncode, 0)

    def test_progress_requires_substantive_reason_and_resume_handles_long_pause(self):
        import task as cli
        directory = self.pending_manual()
        original = (directory/'state.md').read_bytes()
        p = self.run_cli('update', str(directory), '--progress', '--next-action', 'check')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((directory/'state.md').read_bytes(), original)
        p = self.run_cli('update', str(directory), '--progress', '--reason', 'identified root cause', '--next-action', 'test cause')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['calls_since_progress'], '0')

    def test_record_report_mutation_duplicate_and_missing_are_rejected(self):
        directory = self.pending_manual()
        inputs = self.capture(directory)
        self.assertEqual(self.record_manual(directory, inputs).returncode, 0)
        original = (directory/'state.md').read_bytes()
        p = self.record_manual(directory, inputs)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((directory/'state.md').read_bytes(), original)
        (directory/'evidence/observed.md').write_text('changed observation report')
        p = self.run_cli('finish', str(directory))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('report changed', p.stderr)
        self.assertEqual((directory/'state.md').read_bytes(), original)
        self.assertIn('invalid', self.run_cli('summary', str(directory)).stdout)

    def test_nonautomatic_types_and_missing_review_summary(self):
        for kind in ['consumer', 'external']:
            directory = self.fresh_task()
            contract = (directory/'contract.md').read_text().replace('verification_type: automatic', 'verification_type: '+kind)
            (directory/'contract.md').write_text(contract)
            self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
            inputs = self.capture(directory)
            self.assertEqual(self.record_manual(directory, inputs).returncode, 0)
            self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)
            directory.rename(directory.with_name(kind))
        directory = self.pending_manual('user-confirm')
        self.assertIn('审查：not_run', self.run_cli('summary', str(directory)).stdout)

    def test_review_summary_reports_mutation_and_missing_report_is_rejected(self):
        import task as cli
        directory = self.pending_manual('user-confirm')
        inputs = self.capture(directory)
        report = directory/'evidence/review.md'
        report.write_text('Independent review observed result')
        args = ['record', str(directory), '--review', '--evidence', 'review', '--report', 'evidence/review.md',
                '--inputs', inputs, '--observed-at', cli.now(), '--result', 'passed', '--observation', 'review',
                '--reviewer', 'tester', '--source', 'test-run']
        self.assertEqual(self.run_cli(*args).returncode, 0)
        report.write_text('changed after observation')
        self.assertIn('invalid', self.run_cli('summary', str(directory)).stdout)
        directory.rename(directory.with_name('review-task'))
        directory = self.pending_manual()
        inputs = self.capture(directory)
        original = (directory/'state.md').read_bytes()
        p = self.run_cli('record', str(directory), '--acceptance', 'A1', '--evidence', 'missing',
                         '--report', 'evidence/missing.md', '--inputs', inputs, '--observed-at', cli.now(),
                         '--result', 'passed', '--observation', 'checked')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((directory/'state.md').read_bytes(), original)

    def test_update_stale_before_validation_and_record_preserves_concurrent_change(self):
        import task as cli
        from unittest.mock import patch
        directory = self.pending_manual()
        inputs = self.capture(directory)
        report = directory/'evidence/result.md'
        report.write_text('Actual result')
        import argparse
        args = argparse.Namespace(acceptance='A1', review=False, evidence='result', report='evidence/result.md',
                                  inputs=inputs, observed_at=cli.now(), result='passed', observation='checked', reviewer=None, source=None)
        save = cli.save_state
        def changed(task_dir, text, original, contract):
            (directory/'state.md').write_text('concurrent user change')
            save(task_dir, text, original, contract)
        with patch.object(cli, 'save_state', changed), self.assertRaisesRegex(ValueError, 'changed'):
            cli.record(directory, args)
        self.assertEqual((directory/'state.md').read_text(), 'concurrent user change')

    def test_overdue_task_can_record_pause_without_erasing_limits(self):
        directory = self.pending_manual()
        formal = directory/'state.md'
        text = formal.read_text().replace('calls_since_progress: 0', 'calls_since_progress: 20')
        formal.write_text(text)
        p = self.run_cli('update', str(directory), '--status', 'blocked', '--blocked-by', 'no progress',
                         '--unblock-condition', 'new approach', '--next-action', 'inspect failed approach')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['calls_since_progress'], '20')
        p = self.run_cli('update', str(directory), '--status', 'in_progress', '--reason', 'new approach', '--next-action', 'inspect')
        self.assertNotEqual(p.returncode, 0)
        p = self.run_cli('update', str(directory), '--status', 'in_progress', '--progress', '--reason', 'new root cause found', '--next-action', 'test root cause')
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_summary_minimum_recovery_context_and_failed_report_is_immutable(self):
        directory = self.pending_manual()
        inputs = self.capture(directory)
        self.assertEqual(self.record_manual(directory, inputs, 'failure', 'failed').returncode, 0)
        p = self.run_cli('summary', str(directory))
        for value in ['禁止动作：', '风险：', '解除条件：', '下一步：', 'failed', 'evidence/failure.md']:
            self.assertIn(value, p.stdout)
        (directory/'evidence/failure.md').write_text('altered failure report')
        p = self.run_cli('summary', str(directory))
        self.assertIn('invalid', p.stdout)

    def test_summary_malformed_review_reports_invalid_without_traceback(self):
        directory = self.pending_manual('user-confirm')
        formal = directory/'state.md'
        formal.write_text(formal.read_text()+'review_evidence: review|status=passed\n')
        p = self.run_cli('summary', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('invalid', p.stdout)
        self.assertNotIn('Traceback', p.stderr)

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

    def unlimited_contract(self, directory):
        path = directory / 'contract.md'
        contract = path.read_text().replace('## Acceptance',
            'cost_control: unlimited\ncost_authorization: 当前用户：本任务不限制成本\n\n## Acceptance')
        path.write_text(contract)
        return contract

    def test_unlimited_start_run_finish_without_default_deadline(self):
        directory = self.fresh_task()
        contract = self.unlimited_contract(directory).replace('level: L1', 'level: L3')
        (directory / 'contract.md').write_text(contract)
        p = self.run_cli('start', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        fields = checks.check_state(directory)
        self.assertEqual(fields['budget'], 'unlimited')
        self.assertIn('started_at', fields)
        self.assertNotIn('deadline_at', fields)
        p = self.run_verification(directory, "printf 'actual result\\n'")
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.run_cli('finish', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['status'], 'done')

    def test_unlimited_contract_requires_authorization_and_valid_policy(self):
        for value in ['unlimited', 'unknown']:
            with self.subTest(value=value):
                (self.task / 'contract.md').write_text(self.contract.replace('## Acceptance',
                    f'cost_control: {value}\n\n## Acceptance'))
                with self.assertRaisesRegex(ValueError, 'cost_'):
                    checks.check_contract(self.task)
        for source in ['', 'none', '当前用户指令：分析并修复问题']:
            with self.subTest(source=source):
                (self.task / 'contract.md').write_text(self.contract.replace('## Acceptance',
                    f'cost_control: unlimited\ncost_authorization: {source}\n\n## Acceptance'))
                with self.assertRaisesRegex(ValueError, 'cost_authorization'):
                    checks.check_contract(self.task)
        allowed = self.contract.replace('## Acceptance',
            'cost_control: unlimited\ncost_authorization: 当前用户明确说：不限制成本\n\n## Acceptance')
        (self.task / 'contract.md').write_text(allowed)
        checks.check_contract(self.task)

    def test_revise_preserves_history_invalidates_evidence_and_allows_reverify(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'", evidence='before-revise').returncode, 0)
        old_snapshot = (directory / 'audit/contract-r1.md').read_bytes()
        contract = (directory / 'contract.md').read_text().replace('objective: 形成一份局部设计说明', 'objective: 修订后的设计说明')
        (directory / 'contract.md').write_text(contract)
        revised = self.run_cli(
            'revise', str(directory), '--reason', '补充验收范围', '--approved-by', 'current user',
            '--approval-source', 'current user message', '--affected-evidence', 'before-revise',
        )
        self.assertEqual(revised.returncode, 0, revised.stderr)
        self.assertEqual((directory / 'audit/contract-r1.md').read_bytes(), old_snapshot)
        self.assertTrue((directory / 'audit/contract-r2.md').is_file())
        self.assertTrue((directory / 'audit/contract-change-r2.md').is_file())
        state = (directory / 'state.md').read_text()
        self.assertIn('status: in_progress', state)
        self.assertIn('contract_revision: 2', state)
        self.assertIn('required_verification: A1 status=not_run evidence=evidence/before-revise.txt', state)
        checks.check_contract(directory, mode='locked')
        self.assertEqual(self.run_verification(directory, "printf 'actual result\\n'", evidence='after-revise').returncode, 0)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)

    def test_unlimited_state_requires_authorized_contract(self):
        self.assert_bad(self.state.replace('59/60', 'unlimited'), 'cost_authorization')

    def test_unlimited_policy_ignores_existing_budget_and_total_deadline(self):
        contract = self.unlimited_contract(self.task)
        (self.task / 'audit/contract-r1.md').write_text(contract)
        for budget in ['999/60', 'unlimited']:
            for status in ['in_progress', 'done']:
                with self.subTest(budget=budget, status=status):
                    state = (self.state.replace('59/60', budget).replace('status: done', 'status: '+status)
                             .replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(contract.encode()).hexdigest()))
                    state += 'started_at: 2026-09-27T00:00:00Z\ndeadline_at: 2026-09-27T08:00:00Z\nupdated_at: 2026-09-28T15:00:00Z\n'
                    (self.task / 'state.md').write_text(state)
                    checks.check_state(self.task)

    def test_existing_task_can_adopt_unlimited_with_revision_history(self):
        directory = self.fresh_task()
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        original = (directory / 'audit/contract-r1.md').read_bytes()
        contract = self.unlimited_contract(directory).replace('contract_revision: 1', 'contract_revision: 2')
        contract += '\naudit/contract-change-r2.md\n'
        (directory / 'contract.md').write_text(contract)
        (directory / 'audit/contract-change-r2.md').write_text(
            'old_revision: 1\nnew_revision: 2\nold_value: default\nnew_value: unlimited\n'
            'reason: current user removed cost limit\napproved_by: current user\n'
            'approval_source: current user message\naffected_evidence: none; verification not run\n')
        p = self.run_cli('seal', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        state = (directory / 'state.md').read_text()
        state = state.replace('contract_revision: 1', 'contract_revision: 2')
        state = state.replace(hashlib.sha256(original).hexdigest(), hashlib.sha256(contract.encode()).hexdigest())
        state = state.replace('budget: untracked/60', 'budget: unlimited')
        state += 'started_at: 2020-01-01T00:00:00Z\ndeadline_at: 2020-01-01T08:00:00Z\n'
        (directory / 'state.md').write_text(state)
        p = self.run_verification(directory, "printf 'actual result\\n'")
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.run_cli('finish', str(directory))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(checks.check_state(directory)['contract_revision'], '2')
        self.assertEqual((directory / 'audit/contract-r1.md').read_bytes(), original)

    def test_unlimited_keeps_progress_and_acceptance_checks(self):
        contract = self.unlimited_contract(self.task)
        (self.task / 'audit/contract-r1.md').write_text(contract)
        state = (self.state.replace('59/60', 'unlimited')
                 .replace(hashlib.sha256(self.contract.encode()).hexdigest(), hashlib.sha256(contract.encode()).hexdigest()))
        (self.task / 'state.md').write_text(state)
        checks.check_state(self.task)
        self.assert_bad(state.replace('calls_since_progress: 0', 'calls_since_progress: 20'), 'progress')
        self.assert_bad(state.replace('A1 status=passed', 'A1 status=not_run'), 'acceptance')
        self.assert_bad(state.replace('budget: unlimited', 'budget: invalid'), 'budget')
        (self.root / 'input.txt').write_text('changed after verification')
        self.assert_bad(state, 'input changed')

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


def load_tests(loader, tests, pattern):
    spec = importlib.util.spec_from_file_location('work_item_tests', ROOT / 'scripts/test-work-items.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests.addTests(loader.loadTestsFromModule(module))
    return tests


if __name__ == '__main__':
    unittest.main(verbosity=2)
