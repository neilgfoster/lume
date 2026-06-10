import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import GateError
from lume.iteration import Iteration
from lume.workstream import Workstream


def _state_doc(iterations=None, slug="demo", status="active"):
    return {
        "workstream": {
            "slug": slug,
            "title": "Demo",
            "status": status,
            "objective_artifact": "objective.md",
        },
        "iterations": iterations or [],
        "plan": [],
    }


def _write_iteration(ws_dir: Path, id: int, phase: str) -> None:
    it = Iteration(id=id, type="execution", phase=phase, opened="2026-06-01",
                   body=f"# Iteration {id:03d} - t\n")
    (ws_dir / "iterations").mkdir(exist_ok=True)
    (ws_dir / "iterations" / f"{id:03d}.md").write_text(it.to_text())
    (ws_dir / "iterations" / f"{id:03d}.json").write_text(json.dumps(
        {"id": id, "dod": {"preamble": "", "items": []}, "self_review": None, "handback": None},
        indent=2,
    ) + "\n")
    # Update state.json.
    state_path = ws_dir / state_mod.STATE_FILE
    doc = state_mod.load(state_path) if state_path.is_file() else _state_doc()
    doc["iterations"] = [e for e in doc["iterations"] if e["id"] != id]
    doc["iterations"].append(it.to_entity())
    doc["iterations"].sort(key=lambda e: e["id"])
    state_mod.save(state_path, doc)


class OpenIterationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text("# Demo\nobjective\n")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, _state_doc())
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _ws(self) -> Workstream:
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        return Workstream(self.ws_dir, self.clock, doc)

    def test_first_open_creates_001_with_injected_date(self):
        it = self._ws().open_iteration("First")
        self.assertEqual(it.id, 1)
        self.assertEqual(it.phase, "proposed")
        self.assertEqual(it.opened, "2026-01-02")  # from FixedClock, not wall-clock
        self.assertTrue((self.ws_dir / "iterations" / "001.json").is_file())
        self.assertFalse((self.ws_dir / "iterations" / "001.md").exists())

    def test_open_increments_from_highest(self):
        _write_iteration(self.ws_dir, 1, "accepted")
        _write_iteration(self.ws_dir, 2, "accepted")
        it = self._ws().open_iteration("Third")
        self.assertEqual(it.id, 3)
        self.assertTrue((self.ws_dir / "iterations" / "003.json").is_file())

    def test_gate_refuses_when_latest_not_accepted(self):
        _write_iteration(self.ws_dir, 1, "handback")
        with self.assertRaises(GateError) as ctx:
            self._ws().open_iteration("Blocked")
        self.assertIn("001", str(ctx.exception))
        self.assertIn("handback", str(ctx.exception))
        self.assertFalse((self.ws_dir / "iterations" / "002.md").exists())

    def test_gate_allows_when_latest_accepted(self):
        _write_iteration(self.ws_dir, 1, "accepted")
        it = self._ws().open_iteration("Next")
        self.assertEqual(it.id, 2)

    def test_open_touches_only_the_new_file(self):
        _write_iteration(self.ws_dir, 1, "accepted")
        before = (self.ws_dir / "iterations" / "001.md").read_text()
        self._ws().open_iteration("Next")
        after = (self.ws_dir / "iterations" / "001.md").read_text()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
