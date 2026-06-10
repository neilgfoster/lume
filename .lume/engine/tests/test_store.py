"""E1: TrackingStore contract - FilesystemStore behaviour + Repository delegates to it."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume.clock import FixedClock
from lume.errors import LumeError
from lume.repository import Repository
from lume.store import FilesystemStore


def _state_doc(slug="demo"):
    return {
        "workstream": {"slug": slug, "title": "Demo", "status": "active",
                       "objective_artifact": "objective.json"},
        "iterations": [], "plan": [],
    }


class FilesystemStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lume = Path(self._tmp.name) / ".lume"
        (self.lume / "workstreams").mkdir(parents=True)
        self.store = FilesystemStore(self.lume)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_then_has_and_list(self):
        self.assertFalse(self.store.has_workstream("demo"))
        self.store.create_workstream("demo")
        self.store.write("demo", "state", _state_doc())
        self.assertTrue(self.store.has_workstream("demo"))
        self.assertEqual(self.store.list_workstreams(), ["demo"])

    def test_state_round_trip_via_store(self):
        self.store.create_workstream("demo")
        self.store.write("demo", "state", _state_doc())
        got = self.store.read("demo", "state")
        self.assertEqual(got["workstream"]["slug"], "demo")
        # state artifact maps to state.json on disk
        self.assertTrue((self.lume / "workstreams" / "demo" / "state.json").is_file())

    def test_simple_and_iteration_artifacts(self):
        self.store.create_workstream("demo")
        self.store.write("demo", "objective", {"slug": "demo", "x": 1})
        self.store.write("demo", "iteration:003", {"id": 3})
        self.assertEqual(self.store.read("demo", "objective")["x"], 1)
        self.assertEqual(self.store.read("demo", "iteration:003")["id"], 3)
        self.assertTrue(
            (self.lume / "workstreams" / "demo" / "iterations" / "003.json").is_file()
        )

    def test_missing_artifact_returns_none(self):
        self.store.create_workstream("demo")
        self.assertIsNone(self.store.read("demo", "retro"))

    def test_unknown_artifact_id_raises(self):
        with self.assertRaises(ValueError):
            self.store._path("demo", "bogus")


class _RecordingStore:
    """A fake TrackingStore that records calls, to prove Repository delegates."""

    def __init__(self):
        self.calls = []
        self._docs = {}

    def list_workstreams(self):
        self.calls.append(("list",))
        return sorted({slug for (slug, _a) in self._docs})

    def has_workstream(self, slug):
        self.calls.append(("has", slug))
        return (slug, "state") in self._docs

    def create_workstream(self, slug):
        self.calls.append(("create", slug))

    def read(self, slug, artifact):
        self.calls.append(("read", slug, artifact))
        return self._docs.get((slug, artifact))

    def write(self, slug, artifact, doc):
        self.calls.append(("write", slug, artifact))
        self._docs[(slug, artifact)] = doc


class RepositoryDelegatesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.store = _RecordingStore()
        self.repo = Repository(self.root, FixedClock(datetime.date(2026, 6, 10)),
                               store=self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_and_load_state_route_through_store(self):
        self.repo.save_state("demo", _state_doc())
        self.assertIn(("write", "demo", "state"), self.store.calls)
        doc = self.repo.load_state("demo")
        self.assertEqual(doc["workstream"]["slug"], "demo")
        self.assertIn(("read", "demo", "state"), self.store.calls)

    def test_load_state_missing_raises(self):
        with self.assertRaises(LumeError):
            self.repo.load_state("nope")


class CreateWorkstreamViaStoreTest(unittest.TestCase):
    """create_workstream writes state through the store (objective stays on the
    Workstream model until E2), so it is exercised against a real FilesystemStore."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.repo = Repository(self.root, FixedClock(datetime.date(2026, 6, 10)))

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_writes_state_and_objective(self):
        self.repo.create_workstream("demo", "Demo")
        ws_dir = self.root / ".lume" / "workstreams" / "demo"
        self.assertTrue((ws_dir / "state.json").is_file())
        self.assertTrue((ws_dir / "objective.json").is_file())
        # state is loadable back through the store seam
        self.assertEqual(self.repo.load_state("demo")["workstream"]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
