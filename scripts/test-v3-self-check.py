#!/usr/bin/env python3
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "skills" / "x-rail" / "scripts" / "self_check.py"


class SelfCheckTests(unittest.TestCase):
    def test_repo_passes(self):
        result = subprocess.run(["python3", str(CHECK), "--root", str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_oversize_stage_fails(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(ROOT / "skills", tmp / "skills")
        card = tmp / "skills" / "x-rail" / "stages" / "frame.md"
        card.write_text(card.read_text() + ("字" * 7000))
        result = subprocess.run(["python3", str(CHECK), "--root", str(tmp)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frame.md", result.stderr)

    def test_missing_external_skill(self):
        skills = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, skills)
        for name in ("tdd", "code-review", "diagnosing-bugs", "research", "domain-modeling", "grilling"):
            dest = skills / name
            dest.mkdir()
            (dest / "SKILL.md").write_text("---\nname: x\n---\n")
        result = subprocess.run(["python3", str(CHECK), "--root", str(ROOT), "--skills-dir", str(skills)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("codebase-design", result.stderr)


if __name__ == "__main__":
    unittest.main()
