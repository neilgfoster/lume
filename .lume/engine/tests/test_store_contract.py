"""E4: the TrackingStore contract, enforced once across every backing.

This suite is the single source of truth for TrackingStore behaviour. Adding a
future backing (e.g. a GitHub-issues store) means adding it to BACKINGS below -
nothing else - and it must pass identical assertions.
"""
import datetime
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import SchemaError
from lume.repository import Repository
from lume.store import FilesystemStore, InMemoryStore, SQLiteStore


def _state_doc(slug="demo", status="active"):
    return {
        "workstream": {"slug": slug, "title": "Demo", "status": status,
                       "objective_artifact": "objective.json"},
        "iterations": [], "plan": [],
    }


# Each entry: (name, factory). The factory returns a fresh, empty store and an
# optional cleanup callable.
def _fs_factory():
    tmp = tempfile.TemporaryDirectory()
    (Path(tmp.name) / "workstreams").mkdir()
    return FilesystemStore.from_workstreams_root(Path(tmp.name) / "workstreams"), tmp.cleanup


def _sqlite_factory():
    return SQLiteStore(":memory:"), lambda: None


def _memory_factory():
    return InMemoryStore(), lambda: None


BACKINGS = [("fs", _fs_factory), ("sqlite", _sqlite_factory), ("memory", _memory_factory)]


class TrackingStoreContractTest(unittest.TestCase):
    """Identical assertions run against every backing via subTest."""

    def _each(self):
        for name, factory in BACKINGS:
            store, cleanup = factory()
            try:
                yield name, store
            finally:
                cleanup()

    def test_create_returns_id_has_and_list(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id = store.create_workstream("demo")
                store.write(id, "state", _state_doc())
                self.assertTrue(store.has_workstream(id))
                self.assertEqual(store.list_workstreams(), [id])

    def test_has_returns_false_for_unknown_id(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                self.assertFalse(store.has_workstream("0000"))

    def test_sequential_ids_are_distinct(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id1 = store.create_workstream("alpha")
                id2 = store.create_workstream("beta")
                store.write(id1, "state", _state_doc("alpha"))
                store.write(id2, "state", _state_doc("beta"))
                self.assertNotEqual(id1, id2)
                self.assertEqual(sorted(store.list_workstreams()), sorted([id1, id2]))

    def test_round_trip_artifacts(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id = store.create_workstream("demo")
                store.write(id, "state", _state_doc())
                store.write(id, "objective", {"slug": "demo", "x": 1})
                store.write(id, "iteration:003", {"id": 3})
                self.assertEqual(store.read(id, "state")["workstream"]["slug"], "demo")
                self.assertEqual(store.read(id, "objective")["x"], 1)
                self.assertEqual(store.read(id, "iteration:003")["id"], 3)

    def test_missing_returns_none(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id = store.create_workstream("demo")
                self.assertIsNone(store.read(id, "retro"))

    def test_write_upserts(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id = store.create_workstream("demo")
                store.write(id, "state", _state_doc(status="active"))
                store.write(id, "state", _state_doc(status="closed"))
                self.assertEqual(
                    store.read(id, "state")["workstream"]["status"], "closed")

    def test_state_validated_on_write(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                id = store.create_workstream("demo")
                with self.assertRaises(SchemaError):
                    store.write(id, "state",
                                {"workstream": {}, "iterations": [], "plan": []})


class InMemoryStoreTest(unittest.TestCase):
    def test_read_is_isolated_from_stored_copy(self):
        store = InMemoryStore()
        id = store.create_workstream("demo")
        store.write(id, "state", _state_doc())
        got = store.read(id, "state")
        got["workstream"]["status"] = "mutated"
        # Mutating the returned doc must not affect stored state.
        self.assertEqual(store.read(id, "state")["workstream"]["status"], "active")

    def test_lifecycle_against_in_memory_double(self):
        store = InMemoryStore()
        clock = FixedClock(datetime.date(2026, 6, 10))
        with tempfile.TemporaryDirectory() as tmp:
            # .lume/ must exist for Repository resolution; the store stays in-memory
            # so no workstream artifact files are ever written.
            root = Path(tmp)
            (root / ".lume" / "workstreams").mkdir(parents=True)

            def repo():
                return Repository(root, clock, store=store)

            ws = repo().create_workstream("demo", "Demo")
            ws_id = ws.id
            repo().workstream("demo").open_iteration("First", type="execution")
            for verb in ("approve", "start", "handback", "accept"):
                repo().workstream("demo").transition(verb)
            self.assertEqual(
                store.read(ws_id, "state")["iterations"][0]["phase"], "accepted")
            self.assertFalse((root / ".lume" / "workstreams" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
