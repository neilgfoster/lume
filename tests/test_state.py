import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state
from lume.clock import FixedClock
from lume.errors import LumeError, SchemaError
from lume.repository import Repository


def _doc(**over):
    base = {
        "workstream": {
            "slug": "state-as-data",
            "title": "State is Data",
            "status": "active",
            "objective_artifact": "objective.md",
        },
        "iterations": [
            {
                "id": 1,
                "type": "discovery",
                "phase": "accepted",
                "opened": "2026-06-09",
                "title": "Map state",
                "verdicts": [
                    {"date": "2026-06-09", "verdict": "accepted", "reason": None}
                ],
                "dod_artifact": "iterations/001.md",
            }
        ],
        "plan": [
            {
                "id": "P1",
                "type": "execution",
                "iter": 1,
                "tag": "committed",
                "sketch": "schemas",
            }
        ],
    }
    base.update(over)
    return base


class StateRoundTripTest(unittest.TestCase):
    def test_save_then_load_reproduces_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state.save(path, _doc())
            self.assertEqual(state.load(path), _doc())

    def test_resave_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state.save(path, _doc())
            first = path.read_text()
            state.save(path, state.load(path))
            self.assertEqual(path.read_text(), first)

    def test_dump_is_diff_friendly(self):
        text = state.dumps(_doc())
        self.assertTrue(text.endswith("\n"))
        self.assertIn("\n  ", text)  # indented


class StateRejectionTest(unittest.TestCase):
    def test_missing_file_is_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LumeError) as ctx:
                state.load(Path(tmp) / "nope.json")
            self.assertIn("no state", str(ctx.exception))

    def test_malformed_json_is_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{ not json")
            with self.assertRaises(LumeError) as ctx:
                state.load(path)
            self.assertIn("malformed state", str(ctx.exception))

    def test_missing_top_level_key_is_rejected(self):
        bad = _doc()
        del bad["plan"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps(bad))
            with self.assertRaises(LumeError) as ctx:
                state.load(path)
            self.assertIn("plan", str(ctx.exception))

    def test_invalid_entity_is_rejected_on_save_before_writing(self):
        bad = _doc()
        bad["iterations"][0]["phase"] = "bogus"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            with self.assertRaises(SchemaError):
                state.save(path, bad)
            self.assertFalse(path.exists())  # nothing written

    def test_non_array_iterations_is_rejected(self):
        bad = _doc(iterations={})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps(bad))
            with self.assertRaises(LumeError) as ctx:
                state.load(path)
            self.assertIn("iterations", str(ctx.exception))


class RepositorySeamTest(unittest.TestCase):
    def _repo(self, root: Path) -> Repository:
        (root / ".lume" / "workstreams").mkdir(parents=True)
        return Repository(root, FixedClock(datetime.date(2026, 6, 9)))

    def test_save_then_load_state_via_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(Path(tmp))
            repo.save_state("state-as-data", _doc())
            self.assertEqual(repo.load_state("state-as-data"), _doc())

    def test_save_state_creates_workstream_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            repo.save_state("fresh", _doc(workstream={
                "slug": "fresh", "title": "Fresh", "status": "active",
                "objective_artifact": "objective.md",
            }))
            self.assertTrue(
                (root / ".lume" / "workstreams" / "fresh" / "state.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
