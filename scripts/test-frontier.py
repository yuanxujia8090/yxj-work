#!/usr/bin/env python3
"""Public CLI frontier counterexamples. Keep all task artifacts."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('work_fixtures', ROOT/'scripts/test-work-items.py')
assert spec is not None and spec.loader is not None
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def definition(scopes, dependencies=None):
    dependencies = dependencies or {}
    text = 'work_items_schema: 1\nrequirement:R1|outcome=Observable delivery\n'
    for name, scope in scopes.items():
        text += (f'work_item:{name}|title=Delivery {name}|requirements=R1|depends={dependencies.get(name, "none")}'
                 f'|scope={scope}|required=yes|acceptances=A1|skip_reason=none\n')
    return text


class FrontierTests(unittest.TestCase):
    root: Path
    inputs = fixtures.WorkItemTests.inputs
    setUp = fixtures.WorkItemTests.setUp
    prepare = fixtures.WorkItemTests.prepare
    fresh_task = fixtures.WorkItemTests.fresh_task
    start = fixtures.WorkItemTests.start
    run_cli = fixtures.WorkItemTests.run_cli
    run_verification = fixtures.WorkItemTests.run_verification
    capture = fixtures.WorkItemTests.capture
    item = fixtures.WorkItemTests.item
    verify = fixtures.WorkItemTests.verify

    def frontier(self, directory):
        before = {str(p): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        result = self.run_cli('frontier', str(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {str(p): p.read_bytes() for p in directory.rglob('*') if p.is_file()})
        return json.loads(result.stdout)

    def test_cli_ready_and_not_finish(self):
        directory = self.start()
        self.assertEqual(self.frontier(directory)['ready'], ['W1'])
        self.assertNotEqual(self.run_cli('finish', str(directory)).returncode, 0)
        self.verify(directory)
        data = self.frontier(directory)
        self.assertEqual(data['ready'], [])
        self.assertEqual(data['items']['W1']['classification'], 'terminal')
        self.assertEqual(data['task_status'], 'in_progress')

    def test_transitive_stale_dependency_and_independent_sibling(self):
        directory = self.start(definition({'W1':'a', 'W2':'b', 'W3':'c', 'W4':'d'}, {'W2':'W1', 'W3':'W2'}))
        self.verify(directory)
        self.assertEqual(self.item(directory, 'in_progress', 'W2').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification', 'W2').returncode, 0)
        self.assertEqual(self.item(directory, 'verified', 'W2', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)
        self.assertEqual(self.frontier(directory)['ready'], ['W3', 'W4'])
        (self.root/'input.txt').write_text('new input')
        data = self.frontier(directory)
        self.assertEqual(data['ready'], ['W4'])
        self.assertEqual(data['items']['W1']['classification'], 'stale')
        self.assertIn('W2', ' '.join(data['items']['W3']['reasons']))
        self.assertEqual(self.item(directory, 'awaiting_verification', 'W1').returncode, 0)
        self.assertEqual(self.frontier(directory)['ready'], ['W4'])

    def test_active_parent_directory_glob_conflicts_and_candidate_reservations(self):
        directory = self.start(definition({'W1':'src', 'W2':'src/a.py', 'W3':'src/**/*.py', 'W4':'docs/x', 'W5':'docs/y'}))
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        data = self.frontier(directory)
        self.assertEqual(data['ready'], ['W4', 'W5'])
        self.assertEqual(data['items']['W2']['conflicts'], ['W1'])
        self.assertEqual(data['items']['W3']['conflicts'], ['W1'])
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertEqual(self.frontier(directory)['ready'], ['W2', 'W4', 'W5'])
        self.assertEqual(self.item(directory, 'blocked', 'W2', '--item-blocked-by', 'service', '--item-unblock-condition', 'service back').returncode, 0)
        self.assertEqual(self.frontier(directory)['ready'], ['W3', 'W4', 'W5'])

    def test_review_and_paused_task_and_unrelated_change(self):
        directory = self.start(definition({'W1':'a', 'W2':'b'}, {'W2':'W1'}), policy='user-confirm')
        self.assertEqual(self.item(directory, 'in_progress').returncode, 0)
        self.assertEqual(self.item(directory, 'awaiting_verification').returncode, 0)
        self.assertEqual(self.run_verification(directory, "printf 'actual result'").returncode, 0)
        self.assertEqual(self.frontier(directory)['ready'], [])
        self.assertEqual(self.frontier(directory)['items']['W1']['classification'], 'awaiting_verification')
        inputs = self.capture(directory)
        (directory/'evidence/review.md').write_text('Synthetic independent review')
        result = self.run_cli('record', str(directory), '--review', '--evidence', 'review', '--report', 'evidence/review.md',
                              '--inputs', inputs, '--observed-at', fixtures.cli.now(), '--result', 'passed', '--observation', 'review',
                              '--reviewer', 'synthetic reviewer', '--source', 'synthetic-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/actual.txt').returncode, 0)
        (self.root/'unrelated.txt').write_text('unrelated')
        self.assertEqual(self.frontier(directory)['ready'], ['W2'])
        (directory/'evidence/review.md').write_text('Mutated review')
        self.assertEqual(self.frontier(directory)['ready'], [])
        self.assertIn('review', ' '.join(self.frontier(directory)['items']['W2']['reasons']))

    def test_paused_and_terminal_do_not_dispatch(self):
        directory = self.start()
        result = self.run_cli('update', str(directory), '--status', 'blocked', '--blocked-by', 'infra',
                              '--unblock-condition', 'host back', '--next-action', 'query original run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.frontier(directory)['ready'], [])
        self.assertIn('blocked', ' '.join(self.frontier(directory)['items']['W1']['reasons']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
