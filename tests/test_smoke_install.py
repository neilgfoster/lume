"""Clean-repo smoke test: prove a stranger can reach their first iteration.

Drives the bundled `bin/lume` executable (the install entry point) in a fresh
temporary directory that is NOT this repo, following the README's flow: seed a
fresh repo, take the seed discovery iteration through its gates, then create a
workstream and open its first iteration. Exercises the real entry point +
src-layout path resolution end to end, not just an in-process import.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LUME = REPO_ROOT / "plugin" / "bin" / "lume"


class SmokeInstallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def lume(self, *args, expect=0):
        proc = subprocess.run(
            [sys.executable, str(LUME), *args],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, expect,
                         msg=f"lume {' '.join(args)} -> {proc.returncode}: {proc.stderr}")
        return proc.stdout

    def test_stranger_reaches_first_iteration(self):
        # Fresh repo: no .lume/ yet.
        self.assertFalse((self.repo / ".lume").exists())

        # First step from the README: seed bootstraps .lume/ + the seed workstream.
        self.lume("seed", "--new")
        self.assertTrue((self.repo / ".lume" / "workstreams").is_dir())

        # status orients without error and reports the seed's discovery iteration.
        status = json.loads(self.lume("--json", "-w", "0000", "status"))
        self.assertEqual(status["id"], "0000")

        # Drive the seed discovery iteration through the gate sequence.
        for verb in ("approve", "start", "handback", "accept"):
            self.lume("-w", "0000", verb)

        # Create a first real workstream and open its first iteration.
        self.lume("new", "first-goal", "My first goal")
        out = json.loads(self.lume("--json", "-w", "first-goal", "open", "First iteration"))
        self.assertEqual(out["iteration"], 1)
        self.assertEqual(out["phase"], "proposed")


if __name__ == "__main__":
    unittest.main()
