"""P5: verify the state-backed read path and mutation-writes-state-before-views."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.iteration import Iteration
from lume.workstream import Workstream


def _initial_doc(slug="demo", status="active"):
    return {
        "workstream": {
            "slug": slug,
            "title": "Demo",
            "status": status,
            "objective_artifact": "objective.json",
        },
        "iterations": [],
        "plan": [],
    }


def _write_objective_json(ws_dir: Path, slug="demo", status="active") -> None:
    (ws_dir / "objective.json").write_text(json.dumps({
        "slug": slug, "title": "Demo", "status": status, "text": "obj",
    }, indent=2) + "\n")


def _ws(ws_dir: Path, clock: FixedClock) -> Workstream:
    doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
    return Workstream(ws_dir, clock, doc)


class StateBackedReadTest(unittest.TestCase):
    """Reads go through state_doc, not markdown frontmatter."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        self.ws_dir.mkdir()
        (self.ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\nobj\n")
        _write_objective_json(self.ws_dir)
        self.clock = FixedClock(datetime.date(2026, 6, 9))

    def tearDown(self):
        self._tmp.cleanup()

    def test_status_from_state_not_objective_md(self):
        """status comes from state_doc; if we lie in objective.md it is ignored."""
        doc = _initial_doc(status="active")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, doc)
        # Overwrite objective.md to say "closed" — must be ignored.
        (self.ws_dir / "objective.md").write_text("---\nstatus: closed\n---\n# Demo\nobj\n")
        ws = _ws(self.ws_dir, self.clock)
        self.assertEqual(ws.status, "active")
        self.assertFalse(ws.is_closed)

    def test_iterations_from_state_not_markdown_files(self):
        """iterations() uses state_doc; a stale markdown file is ignored."""
        it_entity = {
            "id": 1, "type": "execution", "phase": "accepted",
            "opened": "2026-06-09", "title": "A thing",
            "verdicts": [{"date": "2026-06-09", "verdict": "accepted", "reason": None}],
            "dod_artifact": "iterations/001.json",
        }
        doc = _initial_doc()
        doc["iterations"] = [it_entity]
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, doc)
        # No markdown file written — must not cause an error.
        ws = _ws(self.ws_dir, self.clock)
        its = ws.iterations()
        self.assertEqual(len(its), 1)
        self.assertEqual(its[0].id, 1)
        self.assertEqual(its[0].phase, "accepted")

    def test_current_iteration_from_state(self):
        doc = _initial_doc()
        doc["iterations"] = [{
            "id": 1, "type": "planning", "phase": "handback",
            "opened": "2026-06-09", "title": "Plan it",
            "verdicts": [], "dod_artifact": "iterations/001.json",
        }]
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, doc)
        current = _ws(self.ws_dir, self.clock).current_iteration()
        self.assertIsNotNone(current)
        self.assertEqual(current.phase, "handback")
        self.assertEqual(current.type, "planning")


class MutationWritesStateFirstTest(unittest.TestCase):
    """Mutations update state.json before writing markdown views."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self._tmp.name) / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\nobj\n")
        _write_objective_json(self.ws_dir)
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, _initial_doc())
        self.clock = FixedClock(datetime.date(2026, 6, 9))

    def tearDown(self):
        self._tmp.cleanup()

    def _load_state(self):
        return state_mod.load(self.ws_dir / state_mod.STATE_FILE)

    def test_open_iteration_updates_state_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("New task")
        doc = self._load_state()
        self.assertEqual(len(doc["iterations"]), 1)
        self.assertEqual(doc["iterations"][0]["phase"], "proposed")
        self.assertEqual(doc["iterations"][0]["title"], "New task")
        # Markdown artifact also created.
        self.assertTrue((self.ws_dir / "iterations" / "001.md").is_file())

    def test_transition_updates_state_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        _ws(self.ws_dir, self.clock).transition("approve")
        doc = self._load_state()
        self.assertEqual(doc["iterations"][0]["phase"], "approved")

    def test_accept_writes_verdict_to_state_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        for verb in ("approve", "start", "handback"):
            _ws(self.ws_dir, self.clock).transition(verb)
        _ws(self.ws_dir, self.clock).transition("accept")
        doc = self._load_state()
        self.assertEqual(doc["iterations"][0]["phase"], "accepted")
        verdicts = doc["iterations"][0]["verdicts"]
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "accepted")
        self.assertEqual(verdicts[0]["date"], "2026-06-09")

    def test_set_status_updates_state_and_regenerates_objective_md(self):
        _ws(self.ws_dir, self.clock).set_status("closed")
        doc = self._load_state()
        self.assertEqual(doc["workstream"]["status"], "closed")
        # View regenerated.
        obj = (self.ws_dir / "objective.md").read_text()
        self.assertIn("status: closed", obj)

    def test_plan_md_regenerated_from_state_on_mutation(self):
        """state.plan is the source; plan.md is regenerated as a view on mutation."""
        doc = self._load_state()
        doc["plan"] = [
            {"id": "P1", "type": "execution", "iter": None,
             "tag": "committed", "sketch": "first item"}
        ]
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, doc)
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        plan_text = (self.ws_dir / "plan.md").read_text()
        self.assertIn("P1", plan_text)
        self.assertIn("first item", plan_text)
        # state.plan is unchanged (not re-read from plan.md)
        updated = self._load_state()
        self.assertEqual(updated["plan"][0]["id"], "P1")


if __name__ == "__main__":
    unittest.main()
