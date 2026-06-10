import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import LumeError, NoLumeDirError, NoWorkstreamError
from lume.repository import Repository


def _make_active_ws(lume_dir: Path, slug: str, status: str = "active") -> Path:
    """Write objective.json + objective.md + state.json for a workstream."""
    ws_dir = lume_dir / "workstreams" / slug
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "objective.md").write_text(
        f"---\nstatus: {status}\n---\n# {slug.title()}\nobjective\n"
    )
    (ws_dir / "objective.json").write_text(json.dumps({
        "slug": slug, "title": slug.title(), "status": status, "text": "objective",
    }, indent=2) + "\n")
    state_mod.save(ws_dir / state_mod.STATE_FILE, {
        "workstream": {
            "slug": slug,
            "title": slug.title(),
            "status": status,
            "objective_artifact": "objective.json",
        },
        "iterations": [],
        "plan": [],
    })
    return ws_dir


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
        lume_dir = self.root / ".lume"
        lume_dir.mkdir(parents=True)
        _make_active_ws(lume_dir, "demo")
        repo = Repository(self.root, self.clock)
        self.assertEqual(repo.workstream().name, "demo")

    def test_found_from_a_subdirectory(self):
        lume_dir = self.root / ".lume"
        lume_dir.mkdir(parents=True)
        _make_active_ws(lume_dir, "demo")
        deep = self.root / "a" / "b"
        deep.mkdir(parents=True)
        repo = Repository(deep, self.clock)  # start below the repo root
        self.assertEqual(repo.workstream().name, "demo")

    def test_missing_state_json_not_enumerated(self):
        # A directory with only objective.md and no state.json is not a workstream.
        lume_dir = self.root / ".lume"
        ws_dir = lume_dir / "workstreams" / "demo"
        ws_dir.mkdir(parents=True)
        (ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\n")
        # No state.json created — directory should not be discovered.
        repo = Repository(self.root, self.clock)
        with self.assertRaises(NoWorkstreamError):
            repo.workstream()


if __name__ == "__main__":
    unittest.main()
