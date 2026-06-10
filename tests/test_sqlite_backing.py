"""E3: SQLiteStore second backing, LUME_BACKING selection, and a full lifecycle
exercised against SQLite - replaceability demonstrated, not asserted."""
import datetime
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from lume import state as state_mod
from lume.cli import main
from lume.clock import FixedClock
from lume.errors import SchemaError
from lume.repository import Repository
from lume.store import SQLiteStore


def _state_doc(slug="demo", status="active"):
    return {
        "workstream": {"slug": slug, "title": "Demo", "status": status,
                       "objective_artifact": "objective.json"},
        "iterations": [], "plan": [],
    }


class SQLiteStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteStore(":memory:")

    def test_round_trip_state_and_simple_and_iteration(self):
        id = self.store.create_workstream("demo")
        self.store.write(id, "state", _state_doc())
        self.store.write(id, "objective", {"slug": "demo", "x": 1})
        self.store.write(id, "iteration:003", {"id": 3})
        self.assertEqual(self.store.read(id, "state")["workstream"]["slug"], "demo")
        self.assertEqual(self.store.read(id, "objective")["x"], 1)
        self.assertEqual(self.store.read(id, "iteration:003")["id"], 3)

    def test_missing_returns_none(self):
        id = self.store.create_workstream("demo")
        self.assertIsNone(self.store.read(id, "retro"))

    def test_list_and_has(self):
        id1 = self.store.create_workstream("demo")
        id2 = self.store.create_workstream("other")
        self.store.write(id1, "state", _state_doc())
        self.store.write(id2, "state", _state_doc("other"))
        self.assertTrue(self.store.has_workstream(id1))
        self.assertFalse(self.store.has_workstream("9999"))
        self.assertEqual(self.store.list_workstreams(), [id1, id2])

    def test_write_upserts(self):
        id = self.store.create_workstream("demo")
        self.store.write(id, "state", _state_doc(status="active"))
        self.store.write(id, "state", _state_doc(status="closed"))
        self.assertEqual(self.store.read(id, "state")["workstream"]["status"], "closed")

    def test_state_validated_on_write(self):
        id = self.store.create_workstream("demo")
        with self.assertRaises(SchemaError):
            self.store.write(id, "state", {"workstream": {}, "iterations": [], "plan": []})


class ValidateDocSharedTest(unittest.TestCase):
    """Both stores validate the 'state' artifact through the same state.validate_doc."""

    def test_validate_doc_rejects_bad_state(self):
        with self.assertRaises(SchemaError):
            state_mod.validate_doc({"workstream": {}, "iterations": [], "plan": []})

    def test_validate_doc_accepts_good_state(self):
        state_mod.validate_doc(_state_doc())  # no raise


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args, env=None):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=False):
            with redirect_stdout(out):
                code = main(["lume", *args], start=self.root, clock=self.clock)
        return code, out.getvalue()

    def test_default_fs_writes_files(self):
        code, _ = self._run("new", "alpha", "Alpha")
        self.assertEqual(code, 0)
        ws_root = self.root / ".lume" / "workstreams"
        ws_dir = next(ws_root.glob("*-alpha"))
        self.assertTrue((ws_dir / "state.json").is_file())
        self.assertFalse((self.root / ".lume" / "lume.db").exists())

    def test_sqlite_backing_writes_db_not_files(self):
        code, _ = self._run("new", "beta", "Beta", env={"LUME_BACKING": "sqlite"})
        self.assertEqual(code, 0)
        self.assertTrue((self.root / ".lume" / "lume.db").is_file())
        self.assertFalse((self.root / ".lume" / "workstreams" / "beta" / "state.json").exists())

    def test_unknown_backing_errors(self):
        code, _ = self._run("status", env={"LUME_BACKING": "redis"})
        self.assertEqual(code, 2)


class SqliteLifecycleTest(unittest.TestCase):
    """The full loop runs against a SQLite-injected Repository - no fs workstream files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.store = SQLiteStore(":memory:")
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _repo(self):
        # Fresh Repository sharing the same in-memory store instance.
        return Repository(self.root, self.clock, store=self.store)

    def test_full_lifecycle_on_sqlite(self):
        ws = self._repo().create_workstream("demo", "Demo")
        ws_id = ws.id
        ws.open_iteration("First", type="execution")
        for verb in ("approve", "start", "handback", "accept"):
            self._repo().workstream("demo").transition(verb, note="ok" if verb == "accept" else None)
        # second iteration + decide + retro + close, all via SQLite
        self._repo().workstream("demo").open_iteration("Second", type="closeout")
        self._repo().workstream("demo").add_decision("use sqlite", rationale="proof")
        self._repo().workstream("demo").save_retro(
            {"overall_verdict": "works", "carry_forwards": []})
        self._repo().workstream("demo").set_status("closed")

        # Everything persisted in the db; nothing on the filesystem.
        self.assertEqual(self.store.read(ws_id, "state")["workstream"]["status"], "closed")
        self.assertEqual(len(self.store.read(ws_id, "state")["iterations"]), 2)
        self.assertEqual(self.store.read(ws_id, "decisions")["entries"][0]["decision"], "use sqlite")
        self.assertEqual(self.store.read(ws_id, "retro")["overall_verdict"], "works")
        self.assertFalse((self.root / ".lume" / "workstreams" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
