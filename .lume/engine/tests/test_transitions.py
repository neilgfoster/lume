import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import GateError
from lume.iteration import Iteration, TRANSITIONS
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


def _write_iteration(ws_dir: Path, id: int, phase: str) -> Path:
    it = Iteration(
        id=id, type="execution", phase=phase, opened="2026-06-01",
        body=f"# Iteration {id:03d}\n\n## Verdict\n(none)\n",
    )
    path = ws_dir / "iterations" / f"{id:03d}.md"
    path.write_text(it.to_text())
    # Create minimal NNN.json content artifact.
    json_path = ws_dir / "iterations" / f"{id:03d}.json"
    json_path.write_text(json.dumps(
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
    return path


class TransitionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text("# Demo\nobjective\n")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, _state_doc())
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _ws(self):
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        return Workstream(self.ws_dir, self.clock, doc)

    def test_every_legal_transition(self):
        for verb, (src, dst) in TRANSITIONS.items():
            with self.subTest(verb=verb):
                _write_iteration(self.ws_dir, 1, src)
                result = self._ws().transition(verb, note="x" if verb in ("accept", "reject") else None)
                self.assertEqual(result.phase, dst)

    def test_illegal_transition_from_wrong_phase_refused(self):
        _write_iteration(self.ws_dir, 1, "proposed")
        with self.assertRaises(GateError) as ctx:
            self._ws().transition("accept", note="nope")
        self.assertIn("proposed", str(ctx.exception))
        # phase in state is unchanged
        self.assertEqual(self._ws().current_iteration().phase, "proposed")

    def test_unknown_verb_refused(self):
        _write_iteration(self.ws_dir, 1, "proposed")
        with self.assertRaises(GateError):
            self._ws().transition("teleport")

    def test_non_verdict_transition_updates_phase_in_view(self):
        _write_iteration(self.ws_dir, 1, "proposed")
        self._ws().transition("approve")
        text = (self.ws_dir / "iterations" / "001.md").read_text()
        self.assertIn("phase: approved", text)

    def test_non_verdict_transition_preserves_content_json(self):
        _write_iteration(self.ws_dir, 1, "proposed")
        before = (self.ws_dir / "iterations" / "001.json").read_text()
        self._ws().transition("approve")
        after = (self.ws_dir / "iterations" / "001.json").read_text()
        self.assertEqual(before, after)

    def test_accept_appends_bare_stamp_with_no_reason(self):
        _write_iteration(self.ws_dir, 1, "handback")
        # A note is passed but accept must never record a reason.
        self._ws().transition("accept", note="ignored")
        text = (self.ws_dir / "iterations" / "001.md").read_text()
        self.assertIn("2026-01-02 | ACCEPTED", text)
        self.assertNotIn("ignored", text)
        self.assertNotIn("ACCEPTED |", text)  # no trailing reason segment

    def test_reject_appends_reason(self):
        _write_iteration(self.ws_dir, 1, "handback")
        self._ws().transition("reject", note="DoD too vague")
        text = (self.ws_dir / "iterations" / "001.md").read_text()
        self.assertIn("2026-01-02 | REJECTED | DoD too vague", text)

    def test_full_loop_open_to_accepted(self):
        ws = self._ws()
        ws.open_iteration("End to end")
        for verb in ("approve", "start", "handback"):
            ws.transition(verb)
        ws.transition("accept", note="done")
        self.assertEqual(ws.current_iteration().phase, "accepted")
        # gate now permits opening the next iteration
        nxt = ws.open_iteration("Next one")
        self.assertEqual(nxt.id, 2)


if __name__ == "__main__":
    unittest.main()
