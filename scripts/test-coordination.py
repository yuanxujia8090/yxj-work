#!/usr/bin/env python3
"""Simulated host events through the real CLI, never model execution."""
import importlib.util
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc  # noqa: UP017 - Python 3.10 compatibility

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frontier_fixtures', ROOT/'scripts/test-frontier.py')
assert spec is not None and spec.loader is not None
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class CoordinationTests(unittest.TestCase):
    root: Path
    inputs = fixtures.FrontierTests.inputs
    setUp = fixtures.FrontierTests.setUp
    prepare = fixtures.FrontierTests.prepare
    fresh_task = fixtures.FrontierTests.fresh_task
    start = fixtures.FrontierTests.start
    run_cli = fixtures.FrontierTests.run_cli
    capture = fixtures.FrontierTests.capture
    item = fixtures.FrontierTests.item
    verify = fixtures.FrontierTests.verify
    run_verification = fixtures.FrontierTests.run_verification

    def call(self, command, directory, *args):
        result = self.run_cli(command, str(directory), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def dispatch(self, directory, run='run-1', item='W1', inputs=None):
        inputs = inputs or self.capture(directory, run)
        return self.call('dispatch', directory, '--run', run, '--item', item, '--provider', 'synthetic-host',
                         '--inputs', inputs, '--recovery', 'query original synthetic run')

    def notify(self, directory, event='event-1', run='run-1', outcome='success', *extra):
        return self.call('notify', directory, '--event', event, '--run', run, '--outcome', outcome,
                         '--observed-at', fixtures.fixtures.cli.now(), '--report', 'evidence/child.md' if outcome == 'success' else 'none', *extra)

    def test_queue_cold_start_idempotency_and_no_automatic_verification(self):
        directory = self.start()
        dispatched = self.dispatch(directory)
        self.assertEqual(dispatched['run'], 'run-1')
        self.assertEqual(self.item(directory, 'in_progress', 'W1', '--item-owner', 'run-1').returncode, 0)
        formal = (directory/'state.md').read_bytes()
        (directory/'evidence/child.md').write_text('Synthetic implementation output')
        self.notify(directory)
        store = directory/'audit/coordination.json'
        before = store.read_bytes()
        # Duplicate uses exactly the original factual payload, including occurrence time.
        event = json.loads(before)['events']['event-1']
        self.call('notify', directory, '--event', 'event-1', '--run', 'run-1', '--outcome', 'success',
                  '--observed-at', event['observed_at'], '--report', 'evidence/child.md')
        self.assertEqual(store.read_bytes(), before)
        data = self.call('inbox', directory)
        self.assertEqual([event['event'] for event in data['pending']], ['event-1'])
        self.assertEqual(self.call('consume', directory, '--event', 'event-1')['disposition'], 'accepted')
        consumed = store.read_bytes()
        self.call('consume', directory, '--event', 'event-1')
        self.assertEqual(store.read_bytes(), consumed)
        self.assertEqual(self.call('inbox', directory)['pending'], [])
        self.assertEqual((directory/'state.md').read_bytes(), formal)
        self.assertNotEqual(self.run_cli('finish', str(directory)).returncode, 0)
        self.assertEqual(self.item(directory, 'verified').returncode, 1)

    def test_conflicting_duplicate_and_missing_artifact_preserve_facts(self):
        directory = self.start()
        self.dispatch(directory)
        self.notify(directory)
        store = directory/'audit/coordination.json'
        before = store.read_bytes()
        result = self.run_cli('notify', str(directory), '--event', 'event-1', '--run', 'run-1', '--outcome', 'unknown',
                              '--error', 'exact error', '--observed-at', fixtures.fixtures.cli.now(), '--report', 'evidence/child.md')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(store.read_bytes(), before)
        result = self.run_cli('consume', str(directory), '--event', 'event-1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(store.read_bytes(), before)
        (directory/'evidence/child.md').write_text('Late artifact now available')
        self.assertEqual(self.call('consume', directory, '--event', 'event-1')['disposition'], 'accepted')

    def test_input_change_and_old_run_are_persisted_rejections(self):
        directory = self.start()
        self.dispatch(directory)
        (directory/'evidence/child.md').write_text('Synthetic output')
        (self.root/'input.txt').write_text('changed upstream')
        self.notify(directory)
        result = self.call('consume', directory, '--event', 'event-1')
        self.assertEqual(result['disposition'], 'rejected')
        self.assertIn('input changed', result['reason'])
        self.dispatch(directory, 'run-2')
        self.notify(directory, 'late-event', 'run-1')
        self.assertIn('superseded', self.call('consume', directory, '--event', 'late-event')['reason'])
        self.assertEqual(self.call('inbox', directory)['failure_counts'], {})

    def test_failure_classification_counts_and_sibling_refill(self):
        directory = self.start(fixtures.definition({'W1':'a', 'W2':'b', 'W3':'c'}, {'W3':'W1'}))
        self.dispatch(directory)
        self.item(directory, 'in_progress', 'W1', '--item-owner', 'run-1')
        self.notify(directory, 'event-1', 'run-1', 'capacity', '--error', 'exact host capacity error')
        result = self.call('consume', directory, '--event', 'event-1')
        self.assertEqual(result['disposition'], 'accepted')
        self.item(directory, 'blocked', 'W1', '--item-blocked-by', 'capacity', '--item-unblock-condition', 'smaller scope')
        frontier = self.call('frontier', directory)
        self.assertEqual(frontier['ready'], ['W2'])
        self.assertEqual(self.call('inbox', directory)['failure_counts'], {'W1': {'capacity': 1}})
        self.assertIn('shrink', self.call('inbox', directory)['actions']['capacity'])
        self.dispatch(directory, 'run-2', 'W2')
        self.notify(directory, 'event-2', 'run-2', 'network', '--error', 'exact network error')
        self.call('consume', directory, '--event', 'event-2')
        self.assertEqual(self.call('inbox', directory)['failure_counts']['W2'], {'network': 1})

    def test_systemic_failure_stops_dispatch_and_preserves_original(self):
        directory = self.start(fixtures.definition({'W1':'a', 'W2':'b'}))
        self.dispatch(directory)
        self.notify(directory, 'event-1', 'run-1', 'infrastructure', '--error', 'host protocol EOF', '--systemic')
        self.assertEqual(self.call('frontier', directory)['ready'], [])
        self.assertNotEqual(self.run_cli('consume', str(directory), '--event', 'event-1').returncode, 0)
        self.call('inbox', directory)
        result = self.run_cli('update', str(directory), '--status', 'blocked', '--blocked-by', 'host protocol EOF',
                              '--unblock-condition', 'original host recovered', '--next-action', 'query run-1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.call('consume', directory, '--event', 'event-1')
        runs = self.call('inbox', directory)['runs']
        self.assertEqual(runs['run-1']['recovery'], 'query original synthetic run')

    def test_all_failure_classes_and_counts_survive_new_runs(self):
        directory = self.start()
        for index, outcome in enumerate(['timeout', 'tool', 'acceptance', 'permission', 'unknown', 'network', 'network']):
            run, event = f'run-{index}', f'event-{index}'
            self.dispatch(directory, run)
            self.notify(directory, event, run, outcome, '--error', 'EXACT '+outcome)
            self.call('consume', directory, '--event', event)
        data = self.call('inbox', directory)
        self.assertEqual(data['failure_counts']['W1']['network'], 2)
        self.assertEqual(len(data['runs']), 7)
        self.assertEqual(data['pending'], [])
        self.assertTrue(all(outcome in data['actions'] for outcome in data['failure_counts']['W1']))

    def test_own_output_changes_and_contract_only_dispatch(self):
        directory = self.start(fixtures.definition({'W1':'target.py'}))
        (self.root/'target.py').write_text('old output')
        self.dispatch(directory)
        (self.root/'target.py').write_text('new implementation')
        (directory/'evidence/child.md').write_text('Implementation result')
        self.notify(directory)
        self.assertEqual(self.call('consume', directory, '--event', 'event-1')['disposition'], 'accepted')
        self.assertIn('status=pending', (directory/'state.md').read_text())
        self.dispatch(directory, 'contract-only', inputs='none')
        self.notify(directory, 'contract-event', 'contract-only')
        self.assertEqual(self.call('consume', directory, '--event', 'contract-event')['disposition'], 'accepted')
        self.assertEqual(self.call('inbox', directory)['runs']['contract-only']['manifest']['kind'], 'contract-only')

    def test_completion_rejects_unresolved_original_run(self):
        directory = self.start()
        self.dispatch(directory)
        self.verify(directory)
        result = self.run_cli('finish', str(directory))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unresolved', result.stderr)

    def test_terminal_notifications_reject_new_events_and_preserve_replays(self):
        for terminal in ['done', 'cancelled']:
            with self.subTest(terminal=terminal):
                self.setUp()
                directory = self.start()
                print(f'KEEP terminal-{terminal} fixture: {directory}', flush=True)
                self.dispatch(directory)
                (directory/'evidence/child.md').write_text('Synthetic output')
                event = self.notify(directory)
                self.call('consume', directory, '--event', 'event-1')
                if terminal == 'done':
                    self.verify(directory)
                    result = self.run_cli('finish', str(directory))
                else:
                    result = self.run_cli('update', str(directory), '--status', 'cancelled',
                                          '--reason', 'User cancelled', '--blocked-by', 'User cancelled',
                                          '--unblock-condition', 'none', '--next-action', 'Retain artifacts')
                self.assertEqual(result.returncode, 0, result.stderr)
                before = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
                payload = ['--run', 'run-1', '--outcome', 'success', '--observed-at', event['observed_at'],
                           '--report', 'evidence/child.md']
                late = self.run_cli('notify', str(directory), '--event', 'late-event', *payload)
                self.assertNotEqual(late.returncode, 0, late.stdout)
                self.assertIn('terminal', late.stderr)
                self.call('notify', directory, '--event', 'event-1', *payload)
                conflict = self.run_cli('notify', str(directory), '--event', 'event-1', *payload,
                                        '--error', 'changed payload')
                self.assertNotEqual(conflict.returncode, 0)
                self.assertIn('different content', conflict.stderr)
                self.assertEqual(self.call('inbox', directory)['pending'], [])
                self.call('consume', directory, '--event', 'event-1')
                checked = self.run_cli('check', str(directory))
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(before, {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()})

    def test_real_event_before_registration_is_accepted_but_future_is_rejected(self):
        directory = self.start()
        print(f'KEEP early-event fixture: {directory}', flush=True)
        # A completed host result exists before its original run can be registered.
        (directory/'evidence').mkdir(exist_ok=True)
        (directory/'evidence/child.md').write_text('Host completed before registration')
        observed = datetime.now(UTC).isoformat(timespec='seconds')
        time.sleep(1.05)  # Cross timestamp precision using the real occurrence time.
        run = self.dispatch(directory)
        self.assertLess(observed, run['registered_at'])
        event = self.call('notify', directory, '--event', 'early-event', '--run', 'run-1', '--outcome', 'success',
                          '--observed-at', observed, '--report', 'evidence/child.md')
        self.assertEqual(event['observed_at'], observed)
        self.assertEqual(self.call('consume', directory, '--event', 'early-event')['disposition'], 'accepted')
        before = (directory/'audit/coordination.json').read_bytes()
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat(timespec='seconds')
        rejected = self.run_cli('notify', str(directory), '--event', 'future-event', '--run', 'run-1',
                                '--outcome', 'success', '--observed-at', future, '--report', 'evidence/child.md')
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('future', rejected.stderr)
        self.assertEqual((directory/'audit/coordination.json').read_bytes(), before)

    def test_path_unknown_item_invalid_input_and_active_run_protection(self):
        directory = self.start()
        inputs = self.capture(directory)
        for item, ref in [('W99', inputs), ('W1','../escape.json')]:
            result = self.run_cli('dispatch', str(directory), '--run', 'bad', '--item', item, '--provider', 'host',
                                  '--inputs', ref, '--recovery', 'query')
            self.assertNotEqual(result.returncode, 0)
        self.dispatch(directory)
        result = self.run_cli('dispatch', str(directory), '--run', 'new', '--item', 'W1', '--provider', 'host',
                              '--inputs', inputs, '--recovery', 'query')
        self.assertNotEqual(result.returncode, 0)
        result = self.run_cli('notify', str(directory), '--event', 'escape', '--run', 'run-1', '--outcome', 'success',
                              '--observed-at', fixtures.fixtures.cli.now(), '--report', '../escape.md')
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
