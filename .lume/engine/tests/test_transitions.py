import datetime
import tempfile
import unittest
from pathlib import Path

from lume.clock import FixedClock
from lume.errors import GateError
from lume.iteration import Iteration, TRANSITIONS
from lume.workstream import Workstream


def _write_iteration(ws_dir: Path, id: int, phase: str, body: str | None = None) -> Path:
    it = Iteration(
        id=id, type="build", phase=phase, opened="2026-06-01",
        body=body if body is not None else f"# Iteration {id:03d}\n\n## Verdict\n(none)\n",
    )
    path = ws_dir / "iterations" / f"{id:03d}.md"
    path.write_text(it.to_text())
    return path


class TransitionTest(unittest.TestCase):
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
        # phase on disk is unchanged
        self.assertEqual(self._ws().current_iteration().phase, "proposed")

    def test_unknown_verb_refused(self):
        _write_iteration(self.ws_dir, 1, "proposed")
        with self.assertRaises(GateError):
            self._ws().transition("teleport")

    def test_non_verdict_transition_preserves_body_byte_for_byte(self):
        path = _write_iteration(self.ws_dir, 1, "proposed", body="# Iteration 001\n\nrich body\n## Verdict\n(none)\n")
        before = path.read_text()
        self._ws().transition("approve")
        after = path.read_text()
        # only the phase value differs
        self.assertEqual(before.replace("phase: proposed", "phase: approved"), after)

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
