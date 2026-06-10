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

    def test_create_has_list(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                self.assertFalse(store.has_workstream("demo"))
                store.create_workstream("demo")
                store.write("demo", "state", _state_doc())
                self.assertTrue(store.has_workstream("demo"))
                self.assertEqual(store.list_workstreams(), ["demo"])

    def test_round_trip_artifacts(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                store.write("demo", "state", _state_doc())
                store.write("demo", "objective", {"slug": "demo", "x": 1})
                store.write("demo", "iteration:003", {"id": 3})
                self.assertEqual(store.read("demo", "state")["workstream"]["slug"], "demo")
                self.assertEqual(store.read("demo", "objective")["x"], 1)
                self.assertEqual(store.read("demo", "iteration:003")["id"], 3)

    def test_missing_returns_none(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                self.assertIsNone(store.read("demo", "retro"))

    def test_write_upserts(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                store.write("demo", "state", _state_doc(status="active"))
                store.write("demo", "state", _state_doc(status="closed"))
                self.assertEqual(
                    store.read("demo", "state")["workstream"]["status"], "closed")

    def test_state_validated_on_write(self):
        for name, store in self._each():
            with self.subTest(backing=name):
                with self.assertRaises(SchemaError):
                    store.write("demo", "state",
                                {"workstream": {}, "iterations": [], "plan": []})


class InMemoryStoreTest(unittest.TestCase):
    def test_read_is_isolated_from_stored_copy(self):
        store = InMemoryStore()
        store.write("demo", "state", _state_doc())
        got = store.read("demo", "state")
        got["workstream"]["status"] = "mutated"
        # Mutating the returned doc must not affect stored state.
        self.assertEqual(store.read("demo", "state")["workstream"]["status"], "active")

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

            repo().create_workstream("demo", "Demo")
            repo().workstream("demo").open_iteration("First", type="execution")
            for verb in ("approve", "start", "handback", "accept"):
                repo().workstream("demo").transition(verb)
            self.assertEqual(
                store.read("demo", "state")["iterations"][0]["phase"], "accepted")
            self.assertFalse((root / ".lume" / "workstreams" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
