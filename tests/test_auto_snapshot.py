import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.workstream import Workstream


def _initial_state(slug="demo"):
    return {
        "workstream": {
            "slug": slug,
            "title": "Demo",
            "status": "active",
            "objective_artifact": "objective.json",
        },
        "iterations": [],
        "plan": [],
    }


class DerivedSnapshotTest(unittest.TestCase):
    """JSON-only: the snapshot is derived from state in-memory, never persisted."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.json").write_text(json.dumps({
            "slug": "demo", "title": "Demo", "status": "active", "text": "objective",
        }, indent=2) + "\n")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, _initial_state())
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _ws(self):
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        return Workstream.on_filesystem(self.ws_dir, self.clock, doc)

    def test_no_snapshot_md_written_on_open(self):
        self._ws().open_iteration("First thing")
        self.assertFalse((self.ws_dir / "snapshot.md").exists())

    def test_derive_reflects_open(self):
        self._ws().open_iteration("First thing")
        snap = self._ws().derive_snapshot()
        self.assertIn("## Now\n- 001 First thing - phase proposed", snap)
        self.assertIn("Updated: 2026-01-02 (iteration 001 proposed)", snap)
        self.assertTrue(snap.startswith("# demo - snapshot"))

    def test_derive_reflects_transition(self):
        ws = self._ws()
        ws.open_iteration("First thing")
        self._ws().transition("approve")
        self.assertIn("- 001 First thing - phase approved", self._ws().derive_snapshot())

    def test_full_loop_keeps_derived_snapshot_current(self):
        self._ws().open_iteration("End to end")
        phases = {"approve": "approved", "start": "working", "handback": "handback"}
        for verb, expected in phases.items():
            self._ws().transition(verb)
            self.assertIn(f"phase {expected}", self._ws().derive_snapshot())
        self._ws().transition("accept", note="ignored")
        snap = self._ws().derive_snapshot()
        self.assertIn("- 001 End to end - phase accepted", snap)  # Now
        self.assertIn("## Done\n- 001 End to end", snap)  # also rolled into Done

    def test_snapshot_verb_prints_without_persisting(self):
        ws = self._ws()
        ws.open_iteration("x")
        snap = self._ws().derive_snapshot()
        self.assertIn("## Now", snap)
        self.assertFalse((self.ws_dir / "snapshot.md").exists())


if __name__ == "__main__":
    unittest.main()
