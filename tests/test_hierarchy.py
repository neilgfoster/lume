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

    def test_detail_data_carries_children(self):
        from lume.cli.io import _detail_data
        parent = self.repo.create_workstream("sprint", "Sprint")
        child = self.repo.create_workstream("task-a", "A", parent=parent.id)
        data = _detail_data(parent, self.repo.children(parent.id))
        self.assertIsNone(data["parent"])
        self.assertEqual([c["id"] for c in data["children"]], [child.id])

    def test_queue_data_carries_parent(self):
        from lume.cli.io import _queue_data
        parent = self.repo.create_workstream("sprint", "Sprint")
        child = self.repo.create_workstream("task-a", "A", parent=parent.id)
        data = _queue_data(self.repo.workstreams(self.repo.find_lume_dir()))
        entries = {e["id"]: e for e in data["in_progress"]}
        self.assertEqual(entries[child.id]["parent"], parent.id)
        self.assertIsNone(entries[parent.id]["parent"])

    def test_close_parent_with_active_child_refused(self):
        from lume.cli.context import Context
        parent = self.repo.create_workstream("sprint", "Sprint")
        self.repo.create_workstream("task-a", "A", parent=parent.id)
        from lume.cli.handlers import HANDLERS
        ctx = Context(repo=self.repo, cmd="close", rest=["lume", "close"], arg="",
                      json_mode=True, target="sprint", opt_type=None,
                      opt_context=None, opt_tag=None)
        with self.assertRaises(GateError):
            HANDLERS["close"](ctx)

    def test_close_parent_allowed_once_children_closed(self):
        from lume.cli.context import Context
        from lume.cli.handlers import HANDLERS
        parent = self.repo.create_workstream("sprint", "Sprint")
        child = self.repo.create_workstream("task-a", "A", parent=parent.id)
        child.set_status("closed")
        ctx = Context(repo=self.repo, cmd="close", rest=["lume", "close"], arg="",
                      json_mode=True, target="sprint", opt_type=None,
                      opt_context=None, opt_tag=None)
        self.assertEqual(HANDLERS["close"](ctx), 0)

    def test_reopen_child_under_closed_parent_refused(self):
        parent = self.repo.create_workstream("sprint", "Sprint")
        child = self.repo.create_workstream("task-a", "A", parent=parent.id)
        child.set_status("closed")
        parent.set_status("closed")
        with self.assertRaises(GateError):
            self.repo.reopen_workstream("task-a")

    def test_queue_render_annotates_child(self):
        import io as _io
        from contextlib import redirect_stdout
        from lume.cli.io import _render_queue
        parent = self.repo.create_workstream("sprint", "Sprint")
        self.repo.create_workstream("task-a", "A", parent=parent.id)
        buf = _io.StringIO()
        with redirect_stdout(buf):
            _render_queue(self.repo.workstreams(self.repo.find_lume_dir()))
        self.assertIn("(child of sprint)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
