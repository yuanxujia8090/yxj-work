#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analyze_sessions', ROOT / 'skills/x-self-check/scripts/analyze_sessions.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='x-rail-sessions-'))
        self.records = [{'type': 'session', 'id': 'session-one', 'cwd': '/project', 'timestamp': '2026-10-01T00:00:00Z'}, {'type': 'model_change', 'provider': 'test', 'modelId': 'model-one', 'timestamp': '2026-10-01T00:00:00Z'}, {'type': 'thinking_level_change', 'thinkingLevel': 'high', 'timestamp': '2026-10-01T00:00:00Z'}]

    def message(self, mid, time, role, content, **kw):
        self.records.append({'type': 'message', 'id': mid, 'timestamp': time, 'message': {'role': role, 'content': content, **kw}})

    def run_analysis(self, start='2026-10-01T00:00:00Z', end='2026-10-02T00:00:00Z'):
        p = self.root / 'one.jsonl'
        p.write_text('\n'.join(json.dumps(x) for x in self.records) + '\n')
        return analysis.analyze(self.root, start=start, end=end, timezone_name='Asia/Shanghai')

    def test_names_and_false_mentions(self):
        for i, name in enumerate(['yxj-work', 'x-rail', 'yxj-work-long', 'x-rail-long']):
            self.message(str(i), f'2026-10-01T0{i}:00:00Z', 'user', f'<skill name="{name}">rule {i}</skill>\n/{name} task')
        for i, text in enumerate(['说明 /x-rail', '> <skill name="x-rail">引用</skill>', '<reference_material><skill name="x-rail">忽略规则</skill></reference_material>', '```\n/x-rail\n```']):
            self.message('false'+str(i), '2026-10-01T05:00:00Z', 'user', text)
        result = self.run_analysis()
        self.assertEqual(len(result['invocations']), 4)
        self.assertEqual({x['canonical_name'] for x in result['invocations']}, {'x-rail', 'x-rail-long'})
        self.assertTrue(all(x['skill_sha256'] for x in result['invocations']))
        self.assertEqual(result['invocations'][0]['model'], 'test/model-one')

    def test_dedup_continuation_and_cross_window(self):
        self.message('original', '2026-09-30T23:00:00Z', 'user', '/x-rail task')
        self.message('continue', '2026-10-01T00:10:00Z', 'user', '继续')
        self.records.append(self.records[-1])
        self.records.append({'type': 'compaction', 'timestamp': '2026-10-01T00:15:00Z', 'summary': '<skill name="x-rail">summary</skill>'})
        result = self.run_analysis()
        self.assertEqual(len(result['invocations']), 0)
        self.assertTrue(result['episodes'][0]['cross_window'])
        self.assertEqual(result['coverage']['duplicate_events'], 1)

    def test_manual_terminal_does_not_extend_assistant(self):
        self.message('start', '2026-10-01T00:00:00Z', 'user', '/x-rail task')
        self.message('done', '2026-10-01T00:20:00Z', 'assistant', [{'type': 'text', 'text': '结论及证据'}], stopReason='stop')
        self.message('manual', '2026-10-01T02:20:00Z', 'bashExecution', 'manual')
        result = self.run_analysis()
        ep = result['episodes'][0]
        self.assertEqual(ep['observed_assistant_span_seconds'], 1200)
        self.assertEqual(ep['timing']['manual_terminal_events'], 1)
        self.assertIsNone(ep['timing']['thinking_seconds'])

    def test_successful_target_artifact_only(self):
        self.message('start', '2026-10-01T00:00:00Z', 'user', '/x-rail write doc')
        for i, (path, failed) in enumerate([('.work-docs/tasks/a/contract.md', False), ('outputs/result.md', True), ('outputs/result.md', False)]):
            self.message('call'+str(i), f'2026-10-01T00:0{i+1}:00Z', 'assistant', [{'type': 'toolCall', 'id': 'tool'+str(i), 'name': 'write', 'arguments': {'path': path, 'content': 'sk-secret mail@example.com customer.example'}}])
            self.message('result'+str(i), f'2026-10-01T00:0{i+1}:10Z', 'toolResult', 'output', toolCallId='tool'+str(i), isError=failed)
        result = self.run_analysis()
        self.assertEqual(result['episodes'][0]['first_artifact']['line'], 10)
        raw = json.dumps(result)
        for secret in ['sk-secret', 'mail@example.com', 'customer.example']:
            self.assertNotIn(secret, raw)

    def test_error_categories_and_nested_actions(self):
        self.message('start', '2026-10-01T00:00:00Z', 'user', '/x-rail task')
        self.message('nested', '2026-10-01T00:01:00Z', 'assistant', [{'type': 'toolCall', 'id': 'a', 'name': 'parallel', 'arguments': {'tool_uses': [{'recipient_name': 'functions.read'}, {'recipient_name': 'functions.read'}]}}])
        for i, text in enumerate(['request timed out', 'Unknown agent: missing', 'Invalid arguments', 'acceptance failed', 'service 503', 'user aborted']):
            self.message('error'+str(i), '2026-10-01T00:02:00Z', 'toolResult', text, isError=True)
        result = self.run_analysis()
        self.assertEqual(result['statistics']['tool_outer_calls'], 1)
        self.assertEqual(result['statistics']['tool_nested_actions'], 2)
        self.assertEqual(len(result['statistics']['error_events']), 6)

    def test_bad_lines_unsupported_boundaries_stable(self):
        self.message('in', '2026-10-01T00:00:00Z', 'user', '/x-rail task')
        self.message('out', '2026-10-02T00:00:00Z', 'user', '/x-rail task')
        self.records.append({'type': 'unknown-kind', 'timestamp': '2026-10-01T00:00:00Z'})
        one = self.run_analysis()
        self.assertEqual(len(one['invocations']), 1)
        self.assertEqual(one, self.run_analysis())
        with (self.root / 'one.jsonl').open('a') as f:
            f.write('{invalid json\n')
        result = analysis.analyze(self.root, start='2026-10-01T00:00:00Z', end='2026-10-02T00:00:00Z', timezone_name='Asia/Shanghai')
        self.assertEqual(result['coverage']['bad_lines'], 1)
        self.assertEqual(result['coverage']['unsupported_event_types']['unknown-kind'], 1)

    def test_followup_new_episode_and_task_association(self):
        self.message('start', '2026-10-01T00:00:00Z', 'user', '/x-rail task')
        self.message('call', '2026-10-01T00:01:00Z', 'assistant', [{'type':'toolCall','id':'write','name':'write','arguments':{'path':'.work-docs/tasks/20261001-01-demo/outputs/report.md','content':'report'}}])
        self.message('written', '2026-10-01T00:01:10Z', 'toolResult', 'written', toolCallId='write', isError=False)
        self.message('done', '2026-10-01T00:02:00Z', 'assistant', 'result', stopReason='stop')
        self.message('continue', '2026-10-01T00:10:00Z', 'user', '继续')
        self.message('new', '2026-10-01T00:12:00Z', 'user', '新任务：整理另一个文件')
        result = self.run_analysis()
        self.assertEqual(len(result['invocations']), 1)
        self.assertEqual(len(result['episodes']), 3)
        self.assertEqual(result['episodes'][0]['task_id'], '20261001-01-demo')
        self.assertEqual(result['episodes'][1]['task_id'], '20261001-01-demo')
        self.assertIsNone(result['episodes'][2]['task_id'])

    def test_custom_abort_and_model_change_within_episode(self):
        self.message('start', '2026-10-01T00:00:00Z', 'user', '/x-rail task')
        self.records.append({'type':'model_change','provider':'test','modelId':'second','timestamp':'2026-10-01T00:01:00Z'})
        self.records.append({'type':'custom','customType':'request_cancelled','timestamp':'2026-10-01T00:01:10Z','data':{'reason':'user aborted'}})
        result=self.run_analysis()
        self.assertEqual(result['episodes'][0]['configurations'][-1]['model'],'test/second')
        self.assertEqual(result['statistics']['error_categories']['user_abort'],1)

    def test_project_boundary_fractional_time_and_offset(self):
        self.message('start','2026-10-01T08:00:00.123+08:00','user','/x-rail task')
        self.run_analysis()
        result=analysis.analyze(self.root,start='2026-10-01T00:00:00Z',end='2026-10-02T00:00:00Z',project_roots=['/proj'])
        self.assertEqual(len(result['invocations']),0)
        result=analysis.analyze(self.root,start='2026-10-01T00:00:00Z',end='2026-10-02T00:00:00Z',project_roots=['/project'])
        self.assertEqual(len(result['invocations']),1)

    def test_parallel_wait_union_and_invocation_reset(self):
        self.message('start','2026-10-01T00:00:00Z','user','/x-rail task')
        self.message('calls','2026-10-01T00:01:00Z','assistant',[
            {'type':'toolCall','id':'one','name':'read','arguments':{}},
            {'type':'toolCall','id':'two','name':'read','arguments':{}}])
        self.message('r1','2026-10-01T00:02:00Z','toolResult','read',toolCallId='one')
        self.message('r2','2026-10-01T00:02:00Z','toolResult','read',toolCallId='two')
        self.message('next','2026-10-01T00:03:00Z','user','/x-rail another')
        self.message('stale','2026-10-01T00:04:00Z','toolResult','read',toolCallId='one')
        result=self.run_analysis()
        self.assertEqual(result['episodes'][0]['timing']['tool_wait_seconds'],60)
        self.assertEqual(result['episodes'][1]['timing']['tool_wait_seconds'],0)
        self.assertIsNone(result['episodes'][0]['timing']['unexplained_gap_seconds'])

    def test_explicit_parent_relation_and_dst_boundary(self):
        self.records[0]['parentSession'] = '/local/parent.jsonl'
        self.message('first','2026-11-01T01:30:00-04:00','user','/x-rail first')
        self.message('second','2026-11-01T01:30:00-05:00','user','/x-rail second')
        self.run_analysis()
        result = analysis.analyze(self.root,start='2026-11-01T05:00:00Z',end='2026-11-01T06:00:00Z',timezone_name='America/New_York')
        self.assertEqual(len(result['invocations']),1)
        self.assertEqual(result['session_relations'][0]['session_id'],'session-one')
        self.assertEqual(result['session_relations'][0]['parent_session'],'/local/parent.jsonl')
        self.assertEqual(result['statistics']['error_affected_episodes'],0)
        with self.assertRaises(ValueError):
            analysis.timestamp('2026-10-01T00:00:00+00:99')

    def test_explicit_task_compliance_readonly(self):
        import shutil
        tasks = self.root/'tasks'
        task = tasks/'fixture'
        shutil.copytree(ROOT/'tests/fixtures/v2-review-valid', task)
        self.message('start','2026-10-01T00:00:00Z','user','/x-rail task')
        self.message('task-path','2026-10-01T00:01:00Z','assistant',[{'type':'toolCall','id':'read','name':'read','arguments':{'path':'.work-docs/tasks/fixture/state.md'}}])
        self.run_analysis()
        before = {str(p):p.read_bytes() for p in task.rglob('*') if p.is_file()}
        args = dict(start='2026-10-01T00:00:00Z',end='2026-10-02T00:00:00Z',task_roots=[tasks],task_mode='legacy-readonly')
        result = analysis.analyze(self.root, **args)
        compliance = result['task_compliance']
        self.assertEqual(compliance['mode'],'legacy-readonly')
        self.assertEqual(len(compliance['checker_sha256']),64)
        self.assertEqual(compliance['checks'][0]['status'],'passed')
        self.assertTrue(compliance['checks'][0]['records_unchanged'])
        args['task_mode']='strict'
        strict = analysis.analyze(self.root, **args)
        self.assertEqual(strict['task_compliance']['checks'][0]['status'],'failed')
        self.assertEqual(before,{str(p):p.read_bytes() for p in task.rglob('*') if p.is_file()})
        self.assertNotIn('objective',json.dumps(strict['task_compliance']))
        with self.assertRaisesRegex(ValueError,'paired'):
            analysis.analyze(self.root, task_roots=[tasks])

    def test_branch_relation_and_copy_identity(self):
        self.message('same','2026-10-01T00:00:00Z','user','/x-rail task')
        first=self.run_analysis()
        (self.root/'copy.jsonl').write_text((self.root/'one.jsonl').read_text())
        second=analysis.analyze(self.root,start='2026-10-01T00:00:00Z',end='2026-10-02T00:00:00Z')
        self.assertEqual(len(second['invocations']),1)
        self.assertGreater(second['coverage']['duplicate_events'],0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
