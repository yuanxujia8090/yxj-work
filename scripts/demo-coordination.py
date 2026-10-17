#!/usr/bin/env python3
"""Retained public-CLI rehearsal with synthetic host notifications, no model calls."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('coordination_demo_fixtures', ROOT/'scripts/test-coordination.py')
assert spec is not None and spec.loader is not None
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def main():
    fixture = fixtures.CoordinationTests()
    fixture.setUp()
    transcript = []
    original_cli = fixture.run_cli

    def cli(*args):
        result = original_cli(*args)
        transcript.append({'argv': list(args), 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        return result

    fixture.run_cli = cli
    directory = fixture.start(fixtures.fixtures.definition({'W1': 'src/service.py', 'W2': 'docs/readme.md', 'W3': 'tests/service.py'}, {'W3': 'W1'}))
    fixture.dispatch(directory)
    assert fixture.item(directory, 'in_progress', 'W1', '--item-owner', 'run-1').returncode == 0
    fixture.notify(directory, 'failure-1', 'run-1', 'capacity', '--error', 'SIMULATED host capacity exhausted; original run ended')
    receipt = fixture.call('consume', directory, '--event', 'failure-1')
    assert receipt['disposition'] == 'accepted'
    assert fixture.item(directory, 'blocked', 'W1', '--item-blocked-by', 'capacity', '--item-unblock-condition', 'smaller verified scope').returncode == 0
    assert fixture.call('frontier', directory)['ready'] == ['W2']
    fixture.dispatch(directory, 'run-2', 'W2')
    assert fixture.item(directory, 'in_progress', 'W2', '--item-owner', 'run-2').returncode == 0
    (directory/'evidence/child.md').write_text('SIMULATED independent worker result, still requires actual verification.\n')
    fixture.notify(directory, 'success-2', 'run-2')
    event = fixture.call('inbox', directory)['pending'][0]
    fixture.call('notify', directory, '--event', event['event'], '--run', event['run'], '--outcome', event['outcome'],
                 '--observed-at', event['observed_at'], '--report', event['report'])
    # Every invocation is a new process, so this is a cold-start read, not in-memory recovery.
    assert len(fixture.call('inbox', directory)['pending']) == 1
    assert fixture.call('consume', directory, '--event', 'success-2')['disposition'] == 'accepted'
    assert fixture.item(directory, 'awaiting_verification', 'W2').returncode == 0
    result = fixture.run_verification(directory, "printf 'actual result'")
    assert result.returncode == 0, result.stderr
    assert fixture.item(directory, 'verified', 'W2', '--item-evidence-ref', 'evidence/actual.txt').returncode == 0
    assert cli('finish', str(directory)).returncode != 0
    # A late original result remains a fact and cannot be mistaken for current input verification.
    (fixture.root/'input.txt').write_text('upstream changed after original dispatch\n')
    fixture.notify(directory, 'late-1', 'run-1')
    assert fixture.call('consume', directory, '--event', 'late-1')['disposition'] == 'rejected'
    assert fixture.item(directory, 'in_progress', 'W1', '--item-owner', 'parent').returncode == 0
    assert fixture.item(directory, 'awaiting_verification', 'W1').returncode == 0
    result = cli('run', str(directory), '--acceptance', 'A1', '--evidence', 'refreshed', '--workspace', str(fixture.root),
                 '--input', 'input.txt', '--command', "printf 'actual result'", '--expect', 'actual result')
    assert result.returncode == 0, result.stderr
    assert fixture.item(directory, 'verified', 'W1', '--item-evidence-ref', 'evidence/refreshed.txt').returncode == 0
    assert fixture.item(directory, 'awaiting_verification', 'W2').returncode == 0
    assert fixture.item(directory, 'verified', 'W2', '--item-evidence-ref', 'evidence/refreshed.txt').returncode == 0
    assert fixture.call('frontier', directory)['ready'] == ['W3']
    assert fixture.item(directory, 'in_progress', 'W3', '--item-owner', 'parent').returncode == 0
    assert fixture.item(directory, 'awaiting_verification', 'W3').returncode == 0
    assert fixture.item(directory, 'verified', 'W3', '--item-evidence-ref', 'evidence/refreshed.txt').returncode == 0
    assert fixture.call('frontier', directory)['task_status'] == 'in_progress'
    assert cli('finish', str(directory)).returncode == 0
    assert fixture.call('frontier', directory)['task_status'] == 'done'
    fixture.call('inbox', directory)
    (directory/'outputs').mkdir(exist_ok=True)
    (directory/'outputs/rehearsal.json').write_text(json.dumps({'simulation': True, 'task': str(directory), 'commands': transcript}, ensure_ascii=False, indent=2)+'\n')
    print(f'PASS: synthetic host rehearsal, {len(transcript)} CLI calls; artifacts={directory}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
