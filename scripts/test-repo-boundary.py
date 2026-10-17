#!/usr/bin/env python3
"""A source checkout needs no consumer task tree; existing tasks stay untouched."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepoBoundaryTests(unittest.TestCase):
    def test_clean_source_and_existing_consumer_records(self):
        directory = Path(tempfile.mkdtemp(prefix='x-rail-source-'))
        for name in ['README.md', 'docs', 'scripts', 'skills', 'tests']:
            source = ROOT/name
            if source.is_dir():
                shutil.copytree(source, directory/name, ignore=shutil.ignore_patterns('__pycache__', 'tmp'))
            else:
                shutil.copy2(source, directory/name)
        result = subprocess.run(['bash', str(directory/'scripts/check-repo.sh')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        consumer = directory/'.work-docs'
        consumer.mkdir()
        (consumer/'index.md').write_text('Existing consumer index, never repair it from source checks')
        (consumer/'contract.md').write_text('Existing consumer task')
        before = {p: p.read_bytes() for p in consumer.rglob('*') if p.is_file()}
        result = subprocess.run(['bash', str(directory/'scripts/check-repo.sh')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in consumer.rglob('*') if p.is_file()})
        print(f'consumer records unchanged; artifacts={directory}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
