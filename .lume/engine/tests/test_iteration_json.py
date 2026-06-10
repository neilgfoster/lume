"""P11: iterations/NNN.json as canonical source; NNN.md is a derived view."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import migrate, state as state_mod
from lume.clock import FixedClock
from lume.validate import validate_entity
from lume.workstream import Workstream


def _initial_doc():
    return {
        "workstream": {
            "slug": "demo", "title": "Demo",
            "status": "active", "objective_artifact": "objective.json",
        },
        "iterations": [],
        "plan": [],
    }


def _ws(ws_dir: Path, clock: FixedClock) -> Workstream:
    return Workstream(ws_dir, clock, state_mod.load(ws_dir / state_mod.STATE_FILE))


def _make_ws_dir(tmp: str) -> Path:
    ws_dir = Path(tmp) / "demo"
    (ws_dir / "iterations").mkdir(parents=True)
    (ws_dir / "objective.json").write_text(json.dumps(
        {"slug": "demo", "title": "Demo", "status": "active", "text": "obj"},
        indent=2,
    ) + "\n")
    state_mod.save(ws_dir / state_mod.STATE_FILE, _initial_doc())
    return ws_dir


class OpenIterationJsonTest(unittest.TestCase):
    """open_iteration creates NNN.json; dod_artifact points to it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = _make_ws_dir(self._tmp.name)
        self.clock = FixedClock(datetime.date(2026, 6, 9))

    def tearDown(self):
        self._tmp.cleanup()

    def test_open_creates_nnn_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        self.assertTrue((self.ws_dir / "iterations" / "001.json").is_file())

    def test_open_nnn_json_validates(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        validate_entity("iteration_content", doc)

    def test_dod_artifact_points_to_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        self.assertEqual(doc["iterations"][0]["dod_artifact"], "iterations/001.json")

    def test_open_writes_no_nnn_md_view(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        self.assertFalse((self.ws_dir / "iterations" / "001.md").exists())

    def test_nnn_json_contains_dod_skeleton(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        texts = [i["text"] for i in doc["dod"]["items"]]
        self.assertTrue(any("propose checkable items" in t for t in texts))

    def test_nnn_json_seeded_with_type_skeleton_items(self):
        _ws(self.ws_dir, self.clock).open_iteration("Disc", type="discovery")
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        items = doc["dod"]["items"]
        self.assertTrue(len(items) > 0)
        texts = [i["text"] for i in items]
        self.assertTrue(any("Context built" in t for t in texts))

    def test_nnn_json_has_null_review_and_handback(self):
        _ws(self.ws_dir, self.clock).open_iteration("First")
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        self.assertIsNone(doc["self_review"])
        self.assertIsNone(doc["handback"])


class TransitionStateOnlyTest(unittest.TestCase):
    """transition() mutates state.json only — no NNN.md view, NNN.json untouched."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = _make_ws_dir(self._tmp.name)
        self.clock = FixedClock(datetime.date(2026, 6, 9))

    def tearDown(self):
        self._tmp.cleanup()

    def _state(self):
        return state_mod.load(self.ws_dir / state_mod.STATE_FILE)

    def test_transition_updates_phase_in_state(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        _ws(self.ws_dir, self.clock).transition("approve")
        self.assertEqual(self._state()["iterations"][0]["phase"], "approved")
        self.assertFalse((self.ws_dir / "iterations" / "001.md").exists())

    def test_transition_does_not_modify_nnn_json(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        before = (self.ws_dir / "iterations" / "001.json").read_text()
        _ws(self.ws_dir, self.clock).transition("approve")
        after = (self.ws_dir / "iterations" / "001.json").read_text()
        self.assertEqual(before, after)

    def test_accept_verdict_written_to_state(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        for verb in ("approve", "start", "handback"):
            _ws(self.ws_dir, self.clock).transition(verb)
        _ws(self.ws_dir, self.clock).transition("accept")
        v = self._state()["iterations"][0]["verdicts"][-1]
        self.assertEqual((v["date"], v["verdict"]), ("2026-06-09", "accepted"))

    def test_reject_verdict_with_reason_written_to_state(self):
        _ws(self.ws_dir, self.clock).open_iteration("Task")
        for verb in ("approve", "start", "handback"):
            _ws(self.ws_dir, self.clock).transition(verb)
        _ws(self.ws_dir, self.clock).transition("reject", note="DoD unclear")
        v = self._state()["iterations"][0]["verdicts"][-1]
        self.assertEqual((v["verdict"], v["reason"]), ("rejected", "DoD unclear"))


class MigrateIterationsTest(unittest.TestCase):
    """migrate produces valid NNN.json from legacy NNN.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        lume = self.root / ".lume"
        self.ws_dir = lume / "workstreams" / "legacy"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text(
            "---\nstatus: active\n---\n# Legacy\n\nobj\n"
        )
        (self.ws_dir / "iterations" / "001.md").write_text(
            "---\nid: 001\ntype: execution\nphase: accepted\nopened: 2026-06-09\n---\n"
            "# Iteration 001 - Do thing\n\n## DoD\n- [x] First item\n- [ ] Second\n\n"
            "## Self-review\nLooked good.\n\n## Handback\nShipped.\n\n"
            "## Verdict\n2026-06-09 | ACCEPTED\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _run_migrate(self):
        from lume.repository import Repository
        repo = Repository(self.root, FixedClock(datetime.date(2026, 6, 9)))
        migrate.migrate_all(repo, self.root / ".lume")
        return repo

    def test_migrate_creates_nnn_json(self):
        self._run_migrate()
        self.assertTrue((self.ws_dir / "iterations" / "001.json").is_file())

    def test_migrated_nnn_json_validates(self):
        self._run_migrate()
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        validate_entity("iteration_content", doc)

    def test_migrated_nnn_json_preserves_dod_items(self):
        self._run_migrate()
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        items = doc["dod"]["items"]
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["checked"])
        self.assertIn("First item", items[0]["text"])
        self.assertFalse(items[1]["checked"])

    def test_migrated_nnn_json_preserves_prose_sections(self):
        self._run_migrate()
        doc = json.loads((self.ws_dir / "iterations" / "001.json").read_text())
        self.assertEqual(doc["self_review"], "Looked good.")
        self.assertEqual(doc["handback"], "Shipped.")

    def test_migrate_is_idempotent(self):
        self._run_migrate()
        first = (self.ws_dir / "iterations" / "001.json").read_text()
        self._run_migrate()
        second = (self.ws_dir / "iterations" / "001.json").read_text()
        self.assertEqual(first, second)

    def test_migrate_updates_dod_artifact_in_state(self):
        self._run_migrate()
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        self.assertEqual(doc["iterations"][0]["dod_artifact"], "iterations/001.json")


if __name__ == "__main__":
    unittest.main()
