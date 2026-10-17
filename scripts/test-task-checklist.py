#!/usr/bin/env python3
"""Markdown checklist checker tests."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/x-rail/scripts'

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load_module('work_items', SCRIPTS / 'work_items.py')
task_checks = load_module('task_checks', SCRIPTS / 'task_checks.py')


VALID = """# Task: demo

## Meta
- Created: 2026-10-17T02:00:00Z
- Status: verifying
- Type: bugfix

## Intent
- Goal: 修复过期令牌判断
- Scope: src/auth.py, tests/test_auth.py
- Done when: 回归测试通过且没有新增失败

## Checklist
- [x] 1. 复现失败行为 — evidence: E1
- [x] 2. 修复根因 — evidence: E2
- [ ] 3. 运行完整回归

## Evidence
### E1: 复现
- Command: `python3 tests/test_auth.py`
- Exit: 1
- Result: FAILED（目标用例失败）
- Path: evidence/e1.txt
- Timestamp: 2026-10-17T02:01:00Z

### E2: 修复验证
- Command: `python3 tests/test_auth.py`
- Exit: 0
- Result: PASSED（目标用例通过）
- Path: evidence/e2.txt
- Timestamp: 2026-10-17T02:02:00Z

## Decisions
### D1: 保持接口不变
- Decision: 只修内部比较符
- Reason: 减少影响范围
- Alternatives: 重写认证模块

## Next
- Action: 运行完整回归
- Then: 记录结果
"""


class ChecklistTests(unittest.TestCase):
    def write_task(self, text=VALID):
        root = Path(tempfile.mkdtemp(prefix='x-rail-checklist-')).resolve()
        task = root / 'task.md'
        (root / 'evidence').mkdir()
        (root / 'evidence/e1.txt').write_text('before: failed\n')
        (root / 'evidence/e2.txt').write_text('after: passed\n')
        task.write_text(text)
        return root, task

    def test_valid_checklist(self):
        root, task = self.write_task()
        result = task_checks.check_checklist(task)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['counts']['completed'], 2)

    def test_new_checklist_can_have_no_evidence_before_work_starts(self):
        text = VALID.replace('## Evidence', '## Evidence', 1)
        text = text.replace('- [x] 1. 复现失败行为 — evidence: E1', '- [ ] 1. 复现失败行为')
        text = text.replace('- [x] 2. 修复根因 — evidence: E2', '- [ ] 2. 修复根因')
        root, task = self.write_task(text)
        result = task_checks.check_checklist(task)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['counts']['completed'], 0)

    def test_completed_item_requires_evidence(self):
        root, task = self.write_task(VALID.replace(' — evidence: E2', ''))
        with self.assertRaises(task_checks.ChecklistError) as error:
            task_checks.check_checklist(task)
        self.assertEqual(error.exception.code, 2)
        self.assertIn('evidence', str(error.exception))

    def test_evidence_path_must_exist(self):
        root, task = self.write_task(VALID.replace('evidence/e2.txt', 'evidence/missing.txt'))
        with self.assertRaises(task_checks.ChecklistError) as error:
            task_checks.check_checklist(task)
        self.assertEqual(error.exception.code, 3)
        self.assertIn('not found', str(error.exception))

    def test_cli_error_codes_distinguish_structure_logic_and_evidence(self):
        cases = [
            ('structure', VALID.replace('## Meta', '## Metadata', 1), 1),
            ('logic', VALID.replace(' — evidence: E2', '', 1), 2),
            ('evidence', VALID.replace('evidence/e2.txt', 'evidence/missing.txt', 1), 3),
        ]
        for label, text, expected in cases:
            root, task = self.write_task(text)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'task.py'), 'check', str(task)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected, label + ': ' + result.stderr)

    def test_cli_rejects_task_and_evidence_symlink_boundaries(self):
        for case in ['task-file', 'task-parent', 'evidence-file', 'evidence-parent',
                     'internal-evidence-file', 'internal-evidence-parent']:
            with self.subTest(case=case):
                root, task = self.write_task()
                outside = Path(tempfile.mkdtemp(prefix='x-rail-checklist-outside-')).resolve()
                (outside/'result.txt').write_text('External evidence')
                print(f'KEEP symlink-{case}: task={root}, outside={outside}', flush=True)
                code = 1 if case.startswith('task-') else 3
                if case == 'task-file':
                    alias = root/'alias.md'
                    alias.symlink_to(task)
                    task = alias
                elif case == 'task-parent':
                    alias = outside/'task-alias'
                    alias.symlink_to(root, target_is_directory=True)
                    task = alias/'task.md'
                else:
                    internal = case.startswith('internal-')
                    target = root/'evidence/e2.txt' if internal else outside/'result.txt'
                    if case.endswith('file'):
                        (root/'linked.txt').symlink_to(target)
                        reference = 'linked.txt'
                    else:
                        (root/'linked').symlink_to(target.parent, target_is_directory=True)
                        reference = 'linked/'+target.name
                    task.write_text(VALID.replace('evidence/e2.txt', reference))
                before = task.read_bytes()
                result = subprocess.run([sys.executable, str(SCRIPTS/'task.py'), 'check', str(task)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertRegex(result.stderr, 'symlink|escapes task')
                self.assertEqual(task.read_bytes(), before)
                with self.assertRaises(task_checks.ChecklistError) as error:
                    task_checks.check_checklist(task)
                self.assertEqual(error.exception.code, code)

    def test_cli_checks_file(self):
        root, task = self.write_task()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'task.py'), 'check', str(task)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Result: PASSED', result.stdout)


if __name__ == '__main__':
    unittest.main()
