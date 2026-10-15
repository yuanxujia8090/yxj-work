#!/usr/bin/env python3
"""Work-item protocol counterexamples; all artifacts stay in new temporary roots."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('task_fixtures', ROOT / 'scripts/test-task-checks.py')
assert spec is not None and spec.loader is not None
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
checks = fixtures.checks
cli = __import__('task')

DEFINITION = ('work_items_schema: 1\nrequirement:R1|outcome=Observable result\n'
              'work_item:W1|title=First delivery|requirements=R1|depends=none|scope=input.txt|required=yes|acceptances=A1|skip_reason=none\n')
ROW = ('work_item_state:W1|status=pending|owner=unassigned|evidence_refs=none|commit=none|blocked_by=none'
       '|unblock_condition=none|reason=Not started|next_action=Read input\n')


class WorkItemTests(unittest.TestCase):
    root: Path
    task: Path
    state: str
    contract_text: str
    contract: str
    inputs = fixtures.TaskTests.inputs
    run_cli = fixtures.TaskTests.run_cli
    run_verification = fixtures.TaskTests.run_verification
    capture = fixtures.TaskTests.capture
    record_manual = fixtures.TaskTests.record_manual

    def make_contract(self, definition=DEFINITION):
        return self.contract_text.replace('## Acceptance', definition + '\n## Acceptance')

    def setUp(self):
        fixtures.TaskTests.setUp(self)
        self.contract_text = self.contract
        del self.contract

    def prepare(self, definition=DEFINITION, policy='auto'):
        directory = self.fresh_task()
        text = (directory/'contract.md').read_text().replace('## Acceptance', definition+'\n## Acceptance')
        text = text.replace('review_policy: auto', 'review_policy: '+policy).replace('review: auto', 'review: '+policy)
        (directory/'contract.md').write_text(text)
        return directory

    def fresh_task(self):
        self.contract = self.contract_text
        try:
            return fixtures.TaskTests.fresh_task(self)
        finally:
            del self.contract

    def start(self, definition=DEFINITION, policy='auto'):
        directory = self.prepare(definition, policy)
        result = self.run_cli('start', str(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        return directory

    def item(self, directory, status=None, item='W1', *extra):
        args = ['update', str(directory), '--item', item, '--item-reason', 'Observed event', '--item-next-action', 'Check result']
        if status:
            args += ['--item-status', status]
        return self.run_cli(*args, *extra)

    def assert_failure_unchanged(self, directory, *args):
        index = directory.parent.parent/'index.md'
        if not index.exists():
            index.write_text('| new-task | work | in_progress |\n')
        before = {p: p.read_bytes() for p in [directory/'state.md', directory/'contract.md', index]}
        result = self.run_cli(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        return result

    def verify(self, directory):
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        result = self.run_verification(directory, "printf 'actual result'")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/actual.txt')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_static_counterexamples_and_valid_mapping(self):
        bad = [DEFINITION+ 'requirement:R1|outcome=Duplicate\n',
               DEFINITION+DEFINITION.splitlines()[-1]+'\n',
               DEFINITION+'requirement:R2|outcome=Uncovered\n',
               DEFINITION.replace('requirements=R1', 'requirements=R2'),
               DEFINITION.replace('scope=input.txt|', ''), DEFINITION.replace('acceptances=A1|', ''),
               DEFINITION.replace('required=yes|', ''), DEFINITION.replace('acceptances=A1', 'acceptances=A9'),
               DEFINITION.replace('depends=none', 'depends=W9'), DEFINITION.replace('depends=none', 'depends=W1'),
               DEFINITION.replace('title=First delivery', 'title=First|delivery'),
               DEFINITION.replace('scope=input.txt', 'scope=input.txt,,other'),
               DEFINITION.replace('title=First delivery', 'title=First\nbroken'),
               'work_items_schema: 1\n', DEFINITION.replace('schema: 1', 'schema: 2'),
               DEFINITION.replace('work_items_schema: 1\n', ''),
               DEFINITION.replace('W1|title', '1W|title')]
        second = DEFINITION.splitlines()[-1].replace('W1|', 'W2|').replace('title=First delivery', 'title=Second delivery').replace('depends=none', 'depends=W1')+'\n'
        bad.append(DEFINITION.replace('depends=none', 'depends=W2')+second)
        for definition in bad:
            with self.subTest(definition=definition):
                (self.task/'contract.md').write_text(self.make_contract(definition))
                with self.assertRaises(ValueError):
                    checks.check_contract(self.task)
        valid = DEFINITION+'requirement:R2|outcome=Shared result\n'+second.replace('requirements=R1', 'requirements=R1,R2')
        (self.task/'contract.md').write_text(self.make_contract(valid))
        data = checks.check_contract(self.task)
        self.assertEqual(len(data['work_items']['items']), 2)

    def test_start_initializes_and_repeated_start_preserves(self):
        directory = self.start()
        text = (directory/'state.md').read_text()
        self.assertIn('work_item_state:W1|status=pending', text)
        self.assertIn('active_work_items: none', text)
        self.assertIn('A1 status=not_run', text)
        self.assert_failure_unchanged(directory, 'start', str(directory))

    def test_state_mapping_and_active_counterexamples(self):
        directory = self.start()
        formal = directory/'state.md'
        original = formal.read_text()
        for mutate in [lambda s: s+ROW, lambda s: '\n'.join(x for x in s.splitlines() if not x.startswith('work_item_state:'))+'\n',
                       lambda s: s+ROW.replace('W1|', 'W9|'), lambda s: s.replace('active_work_items: none', 'active_work_items: W1'),
                       lambda s: s.replace('active_work_items: none', 'active_work_items: W9'),
                       lambda s: s.replace('status=pending|', 'status=invented|')]:
            formal.write_text(mutate(original))
            with self.assertRaises(ValueError):
                checks.check_state(directory)
        formal.write_text(original)

    def test_update_requires_identity_reason_action_and_preserves_omitted(self):
        directory = self.start()
        for extra in [('--item', 'W9', '--item-reason', 'reason', '--item-next-action', 'next'),
                      ('--item', 'W1', '--item-status', 'in_progress'),
                      ('--item', 'W1', '--item-reason', 'reason'), ('--item-owner', 'parent'),
                      ('--item', 'W1', '--item-reason', 'bad\ntext', '--item-next-action', 'next'),
                      ('--item', 'W1', '--item-reason', 'bad|text', '--item-next-action', 'next')]:
            self.assert_failure_unchanged(directory, 'update', str(directory), *extra)
        result = self.item(directory, 'in_progress', 'W1', '--item-owner', 'parent', '--item-commit', 'abc')
        self.assertEqual(result.returncode, 0, result.stderr)
        before = checks.check_state(directory)['last_progress_at']
        self.assertEqual(self.item(directory, None).returncode, 0)
        text = (directory/'state.md').read_text()
        self.assertIn('|owner=parent|', text)
        self.assertIn('|commit=abc|', text)
        self.assertIn('active_work_items: W1', text)
        self.assertEqual(checks.check_state(directory)['last_progress_at'], before)
        self.assertEqual(self.item(directory, None, 'W1', '--item-commit', 'none').returncode, 0)
        self.assertIn('|commit=none|', (directory/'state.md').read_text())

    def test_dependency_blocking_and_parallel_active(self):
        second = DEFINITION.splitlines()[-1].replace('W1|', 'W2|').replace('title=First delivery', 'title=Second delivery')+'\n'
        directory = self.start(DEFINITION+second.replace('depends=none', 'depends=W1'))
        self.assertNotEqual(self.item(directory, 'in_progress', 'W2').returncode, 0)
        self.verify(directory)
        self.assertEqual(self.item(directory, 'in_progress', 'W2').returncode, 0)
        self.assertIn('active_work_items: W2', (directory/'state.md').read_text())
        directory.rename(directory.with_name('dependent'))
        directory = self.start(DEFINITION+second)
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'in_progress', 'W2').returncode, 0)
        self.assertIn('active_work_items: W1,W2', (directory/'state.md').read_text())
        self.assertNotEqual(self.item(directory, 'blocked').returncode, 0)
        result = self.item(directory, 'blocked', 'W1', '--item-blocked-by', 'service', '--item-unblock-condition', 'service returns')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli('summary', str(directory))
        self.assertIn('W1: blocked', result.stdout)
        self.assertIn('W2: in_progress', result.stdout)
        self.assertIn('记录状态：in_progress', result.stdout)
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertIn('|reason=Observed event|', (directory/'state.md').read_text())
        self.assertIn('|blocked_by=service|', (directory/'state.md').read_text())
        self.assertEqual(self.item(directory, None, 'W1', '--item-blocked-by', 'none', '--item-unblock-condition', 'none').returncode, 0)
        self.assertIn('|blocked_by=none|', (directory/'state.md').read_text())

    def test_verified_needs_current_acceptance_and_legal_transition(self):
        directory = self.start()
        self.assertNotEqual(self.item(directory, 'verified').returncode, 0)
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertNotEqual(self.item(directory, 'verified', 'W1', '--item-commit', 'abc').returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'wrong'", evidence='failed').returncode, 1)
        self.assertNotEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/failed.txt').returncode, 0)
        self.assertEqual(self.item(directory, 'needs_fix').returncode, 0)
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result'").returncode, 0)
        (self.root/'input.txt').write_text('changed')
        self.assertNotEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)

    def test_completion_staleness_summary_readonly_and_demotion(self):
        directory = self.start()
        self.assert_failure_unchanged(directory, 'finish', str(directory))
        self.verify(directory)
        before = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        result = self.run_cli('summary', str(directory))
        for value in ['需求覆盖：1/1', 'W1: verified', '可执行候选：none', '工作项计数：']:
            self.assertIn(value, result.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()})
        (self.root/'unrelated.txt').write_text('unrelated')
        self.assertIn('W1: verified', self.run_cli('summary', str(directory)).stdout)
        (self.root/'input.txt').write_text('changed')
        self.assertIn('stale', self.run_cli('summary', str(directory)).stdout)
        self.assert_failure_unchanged(directory, 'finish', str(directory))
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertIn('status=awaiting_verification', (directory/'state.md').read_text())

    def test_optional_skip_and_finish_complete(self):
        optional = DEFINITION.splitlines()[-1].replace('W1|', 'W2|').replace('title=First delivery', 'title=Second delivery').replace('required=yes', 'required=no').replace('skip_reason=none', 'skip_reason=Outside this delivery')+'\n'
        directory = self.start(DEFINITION+optional)
        self.assertNotEqual(self.item(directory, 'skipped').returncode, 0)
        self.verify(directory)
        self.assert_failure_unchanged(directory, 'finish', str(directory))
        self.assertEqual(self.item(directory, 'skipped', 'W2').returncode, 0)
        result = self.run_cli('finish', str(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('next_action: ', (directory/'state.md').read_text())
        self.assertNotIn('next_action: 形成', (directory/'state.md').read_text())
        self.assertEqual(checks.check_state(directory)['status'], 'done')

    def test_review_required_before_verified_and_report_mutation(self):
        directory = self.start(policy='user-confirm')
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result'").returncode, 0)
        self.assertNotEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)
        inputs = self.capture(directory)
        (directory/'evidence/review.md').write_text('Independent review')
        result = self.run_cli('record', str(directory), '--review', '--evidence', 'review', '--report', 'evidence/review.md',
                              '--inputs', inputs, '--observed-at', cli.now(), '--result', 'passed', '--observation', 'review',
                              '--reviewer', 'tester', '--source', 'synthetic-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)
        (directory/'evidence/review.md').write_text('Changed review')
        self.assertIn('invalid', self.run_cli('summary', str(directory)).stdout)
        self.assert_failure_unchanged(directory, 'finish', str(directory))

    def test_new_implementation_requires_schema_before_sealing_but_old_tasks_remain(self):
        for kind in ['exec', 'bugfix']:
            directory = self.fresh_task()
            path = directory/'contract.md'
            path.write_text(path.read_text().replace('task_type: design', 'task_type: '+kind))
            original = path.read_bytes()
            result = self.run_cli('start', str(directory))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('work_items_schema', result.stderr)
            self.assertFalse((directory/'audit').exists())
            self.assertFalse((directory/'state.md').exists())
            self.assertEqual(path.read_bytes(), original)
            directory.rename(directory.with_name(kind+'-rejected'))
        directory = self.prepare()
        path = directory/'contract.md'
        path.write_text(path.read_text().replace('task_type: design', 'task_type: mixed'))
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        self.assertIn('work_item_state:W1', (directory/'state.md').read_text())
        # Existing unmarked strict records stay compatible even when their stage is exec.
        self.assertEqual(checks.check_state(self.task)['stage'], 'exec')
        self.assertIn('旧格式', self.run_cli('summary', str(self.task)).stdout)

    def test_optional_acceptance_is_tracked_only_when_referenced(self):
        extra = '\n### A2\noutcome: Optional check\nverification: check\nverification_type: automatic\nlayer: static\nrequired: no\nskip_reason: optional check\n'
        directory = self.prepare(DEFINITION.replace('acceptances=A1', 'acceptances=A2'))
        path = directory/'contract.md'
        path.write_text(path.read_text().replace('## Unknowns', extra+'\n## Unknowns'))
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertNotEqual(self.item(directory, 'verified').returncode, 0)
        result = self.run_cli('run', str(directory), '--acceptance', 'A2', '--evidence', 'optional',
                              '--workspace', str(self.root), '--input', 'input.txt', '--expect', 'ok', '--command', 'printf ok')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/optional.txt').returncode, 0)
        self.assertNotEqual(self.run_cli('finish', str(directory)).returncode, 0)  # A1 still required.
        self.assertEqual(self.run_verification(directory, "printf 'actual result'").returncode, 0)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)
        directory.rename(directory.with_name('optional-automatic'))
        directory = self.prepare(DEFINITION.replace('acceptances=A1', 'acceptances=A2'))
        path = directory/'contract.md'
        path.write_text(path.read_text().replace('## Unknowns', extra.replace('verification_type: automatic', 'verification_type: manual')+'\n## Unknowns'))
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        inputs = self.capture(directory)
        (directory/'evidence/manual.md').write_text('Observed optional result')
        result = self.run_cli('record', str(directory), '--acceptance', 'A2', '--evidence', 'manual',
                              '--report', 'evidence/manual.md', '--inputs', inputs, '--observed-at', cli.now(),
                              '--result', 'passed', '--observation', 'checked optional behavior')
        self.assertEqual(result.returncode, 0, result.stderr)
        directory.rename(directory.with_name('optional-manual'))
        directory = self.prepare()
        path = directory/'contract.md'
        path.write_text(path.read_text().replace('## Unknowns', extra+'\n## Unknowns'))
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        result = self.run_cli('run', str(directory), '--acceptance', 'A2', '--evidence', 'unreferenced',
                              '--workspace', str(self.root), '--input', 'input.txt', '--expect', 'ok', '--command', 'printf ok')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((directory/'evidence/unreferenced.txt').exists())

    def test_optional_skip_keeps_event_reason_and_does_not_pass_acceptance(self):
        optional = DEFINITION.replace('required=yes', 'required=no').replace('skip_reason=none', 'skip_reason=Not needed for release')
        directory = self.start(optional)
        result = self.item(directory, 'skipped')
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (directory/'state.md').read_text()
        self.assertIn('|reason=Observed event|', text)
        self.assertIn('A1 status=not_run', text)
        self.assertNotEqual(self.run_cli('finish', str(directory)).returncode, 0)
        directory.rename(directory.with_name('optional-skipped'))
        directory = self.prepare(optional.replace('skip_reason=Not needed for release', 'skip_reason=none'))
        self.assertNotEqual(self.run_cli('start', str(directory)).returncode, 0)

    def test_skipped_optional_acceptance_does_not_block_finish_when_stale(self):
        optional_acceptance = (
            '\n### A2\n'
            'outcome: Optional check\n'
            'verification: check\n'
            'verification_type: automatic\n'
            'layer: runtime/local\n'
            'required: no\n'
            'skip_reason: optional delivery\n'
        )
        optional_item = (DEFINITION.splitlines()[-1]
                         .replace('W1|', 'W2|')
                         .replace('title=First delivery', 'title=Optional delivery')
                         .replace('acceptances=A1', 'acceptances=A2')
                         .replace('required=yes', 'required=no')
                         .replace('skip_reason=none', 'skip_reason=Outside this delivery') + '\n')
        directory = self.prepare(DEFINITION + optional_item)
        contract = (directory / 'contract.md').read_text().replace(
            '## Unknowns', optional_acceptance + '\n## Unknowns'
        )
        (directory / 'contract.md').write_text(contract)
        self.assertEqual(self.run_cli('start', str(directory)).returncode, 0)
        optional_file = self.root / 'optional.txt'
        optional_file.write_text('optional input\n')
        result = self.run_cli(
            'run', str(directory), '--acceptance', 'A2', '--evidence', 'optional',
            '--workspace', str(self.root), '--input', 'optional.txt', '--expect',
            'optional result', '--command', "printf 'optional result'"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        optional_file.write_text('optional input changed\n')
        with self.assertRaisesRegex(ValueError, 'input changed: optional.txt'):
            checks.check_state(directory)  # A pending item still needs its optional acceptance.
        optional_file.write_text('optional input\n')
        self.assertEqual(self.item(directory, 'skipped', 'W2').returncode, 0)
        self.verify(directory)
        optional_file.write_text('optional input changed\n')
        summary = self.run_cli('summary', str(directory))
        self.assertIn('A2: stale', summary.stdout)
        self.assertIn('W2: skipped', summary.stdout)
        (self.root / 'input.txt').write_text('required input changed\n')
        self.assert_failure_unchanged(directory, 'finish', str(directory))
        (self.root / 'input.txt').write_text('input\n')
        result = self.run_cli('finish', str(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(checks.check_state(directory)['status'], 'done')
        (directory / 'evidence/optional.txt').write_text('')
        with self.assertRaisesRegex(ValueError, 'empty'):
            checks.check_state(directory)  # Skipping never excuses missing historical evidence.

    def test_candidate_active_empty_action_and_item_update_races_preserve(self):
        directory = self.start()
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        candidate = directory/'candidate.md'
        candidate.write_text((directory/'state.md').read_text().replace('status: in_progress', 'status: done'))
        self.assert_failure_unchanged(directory, 'complete', str(directory), '--candidate', str(candidate))
        import argparse
        from unittest.mock import patch
        args = argparse.Namespace(status=None, stage=None, next_action=None, blocked_by=None, unblock_condition=None,
                                  reason=None, progress=False, item='W1', item_reason='event', item_next_action='next',
                                  item_owner='parent')
        original_save = cli.save_state
        def concurrent(task_dir, text, original, contract, verify_items=()):
            (directory/'state.md').write_text('concurrent user edit')
            original_save(task_dir, text, original, contract, verify_items)
        with patch.object(cli, 'save_state', concurrent), self.assertRaisesRegex(ValueError, 'changed'):
            cli.update(directory, args)
        self.assertEqual((directory/'state.md').read_text(), 'concurrent user edit')

    def test_predecessor_repair_preserves_successor_and_blocks_verification(self):
        second = DEFINITION.splitlines()[-1].replace('W1|', 'W2|').replace('title=First delivery', 'title=Second delivery').replace('depends=none', 'depends=W1')+'\n'
        directory = self.start(DEFINITION+second)
        self.verify(directory)
        self.assertEqual(self.item(directory, 'in_progress', 'W2').returncode, 0)
        (self.root/'input.txt').write_text('changed predecessor input')
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertIn('work_item_state:W2|status=in_progress', (directory/'state.md').read_text())
        self.assertNotEqual(self.item(directory, 'awaiting_verification', 'W2').returncode, 0)
        self.assertNotEqual(self.item(directory, 'verified', 'W2', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)
        self.assert_failure_unchanged(directory, 'finish', str(directory))
        result = self.run_verification(directory, "printf 'actual result'", evidence='current')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/current.txt').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification', 'W2').returncode, 0)
        self.assertEqual(self.item(directory, 'verified', 'W2', '--item-evidence-ref', 'evidence/current.txt').returncode, 0)
        self.assertEqual(self.run_cli('finish', str(directory)).returncode, 0)

    def test_complete_rejects_unchanged_next_action_and_contract_mutation(self):
        directory = self.start()
        self.verify(directory)
        formal = directory/'state.md'
        candidate = directory/'candidate.md'
        candidate.write_text(cli.state_text(formal.read_text(), {'status': 'done'}))
        result = self.assert_failure_unchanged(directory, 'complete', str(directory), '--candidate', str(candidate))
        self.assertIn('next_action', result.stderr)
        contract = directory/'contract.md'
        contract.write_text(contract.read_text()+'\nunauthorized checklist change\n')
        result = self.run_cli('finish', str(directory))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('contract changed', result.stderr)

    def test_complete_and_concurrent_changes_preserve_formal_state(self):
        directory = self.start()
        self.verify(directory)
        formal = directory/'state.md'
        candidate = directory/'candidate.md'
        candidate.write_text(cli.state_text(formal.read_text(), {'status': 'done', 'next_action': '交付结果并结束'}))
        def mutate():
            formal.write_text(formal.read_text()+'concurrent user change\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cli.complete(directory, candidate, before_commit=mutate)
        self.assertIn('concurrent user change', formal.read_text())
        result = self.run_cli('complete', str(directory), '--candidate', str(candidate))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
