import datetime
import tempfile
import unittest
from pathlib import Path

from lume.clock import FixedClock
from lume.workstream import Workstream


class AutoSnapshotTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text("# Demo\nobjective\n")
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _ws(self):
        return Workstream(self.ws_dir, self.clock)

    def _snapshot(self) -> str:
        return (self.ws_dir / "snapshot.md").read_text()

    def test_open_refreshes_snapshot(self):
        self._ws().open_iteration("First thing")
        snap = self._snapshot()
        self.assertIn("## Now\n- 001 First thing - phase proposed", snap)
        self.assertIn("Updated: 2026-01-02 (iteration 001 proposed)", snap)
        # title seeded from the workstream name when no snapshot existed
        self.assertTrue(snap.startswith("# demo - snapshot"))

    def test_transition_refreshes_snapshot_now_phase(self):
        ws = self._ws()
        ws.open_iteration("First thing")
        ws.transition("approve")
        self.assertIn("- 001 First thing - phase approved", self._snapshot())

    def test_full_loop_keeps_snapshot_current_without_explicit_snapshot_call(self):
        ws = self._ws()
        ws.open_iteration("End to end")
        phases = {"approve": "approved", "start": "working", "handback": "handback"}
        for verb, expected in phases.items():
            ws.transition(verb)
            self.assertIn(f"phase {expected}", self._snapshot())
        ws.transition("accept", note="ignored")
        snap = self._snapshot()
        self.assertIn("- 001 End to end - phase accepted", snap)  # Now
        self.assertIn("## Done\n- 001 End to end", snap)  # also rolled into Done

    def test_next_section_survives_folded_refresh(self):
        ws = self._ws()
        ws.open_iteration("x")
        # hand-edit the Next section, then drive a transition
        snap_path = self.ws_dir / "snapshot.md"
        snap_path.write_text(snap_path.read_text().replace("## Next\n", "## Next\n- my plan\n"))
        ws.transition("approve")
        self.assertIn("## Next\n- my plan", snap_path.read_text())

    def test_standalone_snapshot_still_works(self):
        ws = self._ws()
        ws.open_iteration("x")
        path = ws.record_snapshot()
        self.assertEqual(path.name, "snapshot.md")
        self.assertIn("## Now", path.read_text())


if __name__ == "__main__":
    unittest.main()
