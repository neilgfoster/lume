"""P10: objective.json as canonical source; objective.md is a derived view."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import migrate, state as state_mod
from lume.clock import FixedClock
from lume.errors import NoWorkstreamError
from lume.repository import Repository
from lume.validate import validate_entity


def _repo(root: Path) -> Repository:
    return Repository(root, FixedClock(datetime.date(2026, 6, 9)))


def _make_lume(root: Path) -> Path:
    lume = root / ".lume"
    (lume / "workstreams").mkdir(parents=True)
    return lume


class CreateWorkstreamObjectiveTest(unittest.TestCase):
    """lume new creates objective.json; objective.md is a regenerated view."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _make_lume(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_writes_objective_json(self):
        ws = _repo(self.root).create_workstream("alpha", "Alpha Initiative")
        obj_path = self.root / ".lume" / "workstreams" / "alpha" / "objective.json"
        self.assertTrue(obj_path.is_file())

    def test_objective_json_passes_schema_validation(self):
        _repo(self.root).create_workstream("alpha", "Alpha Initiative")
        obj_path = self.root / ".lume" / "workstreams" / "alpha" / "objective.json"
        doc = json.loads(obj_path.read_text())
        validate_entity("objective", doc)  # raises on failure

    def test_objective_json_fields_match_inputs(self):
        _repo(self.root).create_workstream("beta", "Beta Run")
        obj_path = self.root / ".lume" / "workstreams" / "beta" / "objective.json"
        doc = json.loads(obj_path.read_text())
        self.assertEqual(doc["slug"], "beta")
        self.assertEqual(doc["title"], "Beta Run")
        self.assertEqual(doc["status"], "active")

    def test_create_also_writes_objective_md_view(self):
        _repo(self.root).create_workstream("gamma", "Gamma Plan")
        md = (self.root / ".lume" / "workstreams" / "gamma" / "objective.md").read_text()
        self.assertIn("Gamma Plan", md)
        self.assertIn("status: active", md)

    def test_objective_md_is_regenerated_not_authored(self):
        """Corrupting objective.md and re-reading does not affect the canonical data."""
        ws = _repo(self.root).create_workstream("delta", "Delta Goal")
        ws_dir = self.root / ".lume" / "workstreams" / "delta"
        # Corrupt the view file.
        (ws_dir / "objective.md").write_text("---\nstatus: closed\n---\n# CORRUPTED\n")
        # The canonical title still comes from state (via objective_line).
        self.assertEqual(ws.objective_line(), "Delta Goal")
        # The canonical status still comes from state.json.
        doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
        self.assertEqual(doc["workstream"]["status"], "active")


class SetStatusObjectiveTest(unittest.TestCase):
    """set_status keeps objective.json and state.json in sync."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _make_lume(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_set_status_updates_objective_json(self):
        ws = _repo(self.root).create_workstream("ws", "My WS")
        ws.set_status("closed")
        ws_dir = self.root / ".lume" / "workstreams" / "ws"
        obj = json.loads((ws_dir / "objective.json").read_text())
        self.assertEqual(obj["status"], "closed")

    def test_set_status_regenerates_objective_md(self):
        ws = _repo(self.root).create_workstream("ws", "My WS")
        ws.set_status("closed")
        ws_dir = self.root / ".lume" / "workstreams" / "ws"
        md = (ws_dir / "objective.md").read_text()
        self.assertIn("status: closed", md)

    def test_set_status_objective_json_remains_valid(self):
        ws = _repo(self.root).create_workstream("ws", "My WS")
        ws.set_status("closed")
        ws_dir = self.root / ".lume" / "workstreams" / "ws"
        validate_entity("objective", json.loads((ws_dir / "objective.json").read_text()))


class MigrateObjectiveTest(unittest.TestCase):
    """migrate_objective produces a valid objective.json from a legacy objective.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        lume = _make_lume(self.root)
        self.ws_dir = lume / "workstreams" / "legacy"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.md").write_text(
            "---\nstatus: active\n---\n# Legacy Work\n\nDo the legacy thing.\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_migrate_creates_objective_json(self):
        repo = _repo(self.root)
        migrate.migrate_all(repo, self.root / ".lume")
        self.assertTrue((self.ws_dir / "objective.json").is_file())

    def test_migrated_objective_json_validates(self):
        repo = _repo(self.root)
        migrate.migrate_all(repo, self.root / ".lume")
        doc = json.loads((self.ws_dir / "objective.json").read_text())
        validate_entity("objective", doc)

    def test_migrated_objective_json_preserves_prose(self):
        repo = _repo(self.root)
        migrate.migrate_all(repo, self.root / ".lume")
        doc = json.loads((self.ws_dir / "objective.json").read_text())
        self.assertIn("legacy thing", doc["text"])
        self.assertEqual(doc["title"], "Legacy Work")
        self.assertEqual(doc["status"], "active")

    def test_migrate_objective_is_idempotent(self):
        repo = _repo(self.root)
        migrate.migrate_all(repo, self.root / ".lume")
        first = (self.ws_dir / "objective.json").read_text()
        migrate.migrate_all(repo, self.root / ".lume")
        second = (self.ws_dir / "objective.json").read_text()
        self.assertEqual(first, second)

    def test_migrate_renders_objective_md_as_view(self):
        repo = _repo(self.root)
        migrate.migrate_all(repo, self.root / ".lume")
        md = (self.ws_dir / "objective.md").read_text()
        # The rendered view should contain slug/status frontmatter from objective.json.
        self.assertIn("slug: legacy", md)
        self.assertIn("status: active", md)
        self.assertIn("Legacy Work", md)


if __name__ == "__main__":
    unittest.main()
