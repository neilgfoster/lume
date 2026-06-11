"""Parent/child workstreams: parent ref, spawn, children-by-scan (P4/L3, P19)."""
import datetime
import tempfile
import unittest
from pathlib import Path

from lume.clock import FixedClock
from lume.errors import GateError
from lume.repository import Repository


class HierarchyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root_dir = Path(self._tmp.name)
        self.repo = Repository(self.root_dir, FixedClock(datetime.date(2026, 1, 2)))
        self.repo.ensure_lume_dir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_root_has_no_parent(self):
        ws = self.repo.create_workstream("root", "Root")
        self.assertIsNone(ws.parent)

    def test_spawn_links_child_to_parent(self):
        parent = self.repo.create_workstream("sprint", "Sprint")
        child = self.repo.create_workstream("task-a", "Task A", parent=parent.id)
        self.assertEqual(child.parent, parent.id)

    def test_children_derived_by_scan(self):
        parent = self.repo.create_workstream("sprint", "Sprint")
        self.repo.create_workstream("other", "Other root")  # not a child
        c1 = self.repo.create_workstream("task-a", "A", parent=parent.id)
        c2 = self.repo.create_workstream("task-b", "B", parent=parent.id)
        child_ids = {c.id for c in self.repo.children(parent.id)}
        self.assertEqual(child_ids, {c1.id, c2.id})

    def test_missing_parent_errors(self):
        with self.assertRaises(GateError):
            self.repo.create_workstream("orphan", "Orphan", parent="9999")


if __name__ == "__main__":
    unittest.main()
