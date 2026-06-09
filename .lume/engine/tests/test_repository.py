import datetime
import tempfile
import unittest
from pathlib import Path

from lume.clock import FixedClock
from lume.errors import NoLumeDirError, NoWorkstreamError
from lume.repository import Repository


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_lume_dir_raises(self):
        repo = Repository(self.root, self.clock)
        with self.assertRaises(NoLumeDirError):
            repo.workstream()

    def test_lume_dir_but_no_workstream_raises(self):
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        repo = Repository(self.root, self.clock)
        with self.assertRaises(NoWorkstreamError):
            repo.workstream()

    def test_resolves_sole_active_workstream(self):
        ws_dir = self.root / ".lume" / "workstreams" / "demo"
        ws_dir.mkdir(parents=True)
        (ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\nobjective\n")
        repo = Repository(self.root, self.clock)
        self.assertEqual(repo.workstream().name, "demo")

    def test_found_from_a_subdirectory(self):
        ws_dir = self.root / ".lume" / "workstreams" / "demo"
        ws_dir.mkdir(parents=True)
        (ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\nobjective\n")
        deep = self.root / "a" / "b"
        deep.mkdir(parents=True)
        repo = Repository(deep, self.clock)  # start below the repo root
        self.assertEqual(repo.workstream().name, "demo")


if __name__ == "__main__":
    unittest.main()
