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
        id = self.store.create_workstream("demo")
        self.assertFalse(self.store.has_workstream("ghost"))
        self.store.write(id, "state", _state_doc())
        self.assertTrue(self.store.has_workstream(id))
        self.assertEqual(self.store.list_workstreams(), [id])

    def test_sequential_ids_and_folder_names(self):
        id1 = self.store.create_workstream("alpha")
        id2 = self.store.create_workstream("beta")
        self.assertNotEqual(id1, id2)
        self.assertTrue((self.lume / "workstreams" / f"{id1}-alpha").is_dir())
        self.assertTrue((self.lume / "workstreams" / f"{id2}-beta").is_dir())

    def test_state_round_trip_via_store(self):
        id = self.store.create_workstream("demo")
        self.store.write(id, "state", _state_doc())
        got = self.store.read(id, "state")
        self.assertEqual(got["workstream"]["slug"], "demo")
        self.assertTrue((self.lume / "workstreams" / f"{id}-demo" / "state.json").is_file())

    def test_simple_and_iteration_artifacts(self):
        id = self.store.create_workstream("demo")
        self.store.write(id, "objective", {"slug": "demo", "x": 1})
        self.store.write(id, "iteration:003", {"id": 3})
        self.assertEqual(self.store.read(id, "objective")["x"], 1)
        self.assertEqual(self.store.read(id, "iteration:003")["id"], 3)
        self.assertTrue(
            (self.lume / "workstreams" / f"{id}-demo" / "iterations" / "003.json").is_file()
        )

    def test_missing_artifact_returns_none(self):
        id = self.store.create_workstream("demo")
        self.assertIsNone(self.store.read(id, "retro"))

    def test_unknown_artifact_id_raises(self):
        with self.assertRaises(ValueError):
            self.store._path("0001", "bogus")


class _RecordingStore:
    """A fake TrackingStore that records calls, to prove Repository delegates."""

    def __init__(self):
        self.calls = []
        self._docs = {}
        self._counter = 0

    def list_workstreams(self):
        self.calls.append(("list",))
        return sorted({id for (id, _a) in self._docs if _a == "state"})

    def has_workstream(self, id):
        self.calls.append(("has", id))
        return (id, "state") in self._docs

    def create_workstream(self, slug, seed=False):
        self._counter += 1
        id = str(self._counter).zfill(4)
        self.calls.append(("create", slug))
        return id

    def read(self, id, artifact):
        self.calls.append(("read", id, artifact))
        return self._docs.get((id, artifact))

    def write(self, id, artifact, doc):
        self.calls.append(("write", id, artifact))
        self._docs[(id, artifact)] = doc


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
        self.repo.save_state("0001", _state_doc())
        self.assertIn(("write", "0001", "state"), self.store.calls)
        doc = self.repo.load_state("0001")
        self.assertEqual(doc["workstream"]["slug"], "demo")
        self.assertIn(("read", "0001", "state"), self.store.calls)

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
        ws = self.repo.create_workstream("demo", "Demo")
        # Folder is NNNN-demo; find it dynamically
        ws_root = self.root / ".lume" / "workstreams"
        ws_dir = next(ws_root.glob("*-demo"))
        self.assertTrue((ws_dir / "state.json").is_file())
        self.assertTrue((ws_dir / "objective.json").is_file())
        # state is loadable back through the store seam using the minted id
        self.assertEqual(self.repo.load_state(ws.id)["workstream"]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
