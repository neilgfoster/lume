"""P14: discovery.json as data + the `lume reopen` verb."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import cli, migrate, state as state_mod
from lume.clock import FixedClock
from lume.discovery import parse_discovery_md
from lume.errors import SchemaError
from lume.repository import Repository
from lume.validate import validate_entity


_SAMPLE = """# demo - discovery

intro line ignored (before first ##)

## 1. First section

body of first
- a bullet

### a subsection
kept verbatim

## 2. Second section

second body
"""


class DiscoverySchemaTest(unittest.TestCase):
    def test_valid_doc_passes(self):
        validate_entity("discovery", {
            "title": "t", "sections": [{"heading": "h", "body": "b"}],
        })

    def test_missing_sections_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("discovery", {"title": "t"})

    def test_section_missing_body_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("discovery", {"sections": [{"heading": "h"}]})

    def test_title_optional(self):
        validate_entity("discovery", {"sections": []})


class ParseDiscoveryTest(unittest.TestCase):
    def test_parse_title_and_sections(self):
        doc = parse_discovery_md(_SAMPLE)
        self.assertEqual(doc["title"], "demo - discovery")
        self.assertEqual([s["heading"] for s in doc["sections"]],
                         ["1. First section", "2. Second section"])

    def test_nested_subsection_kept_in_body(self):
        doc = parse_discovery_md(_SAMPLE)
        self.assertIn("### a subsection", doc["sections"][0]["body"])
        self.assertIn("- a bullet", doc["sections"][0]["body"])

    def test_result_validates(self):
        validate_entity("discovery", parse_discovery_md(_SAMPLE))


class MigrateDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ws_dir = self.root / ".lume" / "workstreams" / "demo"
        (self.ws_dir / "iterations").mkdir(parents=True)
        (self.ws_dir / "objective.json").write_text(json.dumps(
            {"slug": "demo", "title": "Demo", "status": "active", "text": "o"}) + "\n")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, {
            "workstream": {"slug": "demo", "title": "Demo", "status": "active",
                           "objective_artifact": "objective.json"},
            "iterations": [], "plan": [],
        })

    def tearDown(self):
        self._tmp.cleanup()

    def _repo(self):
        return Repository(self.root, FixedClock(datetime.date(2026, 6, 10)))

    def test_migrate_creates_discovery_json(self):
        (self.ws_dir / "discovery.md").write_text(_SAMPLE)
        migrate.migrate_all(self._repo(), self.root / ".lume")
        doc = json.loads((self.ws_dir / "discovery.json").read_text())
        validate_entity("discovery", doc)
        self.assertEqual(doc["title"], "demo - discovery")

    def test_migrate_no_op_without_discovery_md(self):
        migrate.migrate_all(self._repo(), self.root / ".lume")
        self.assertFalse((self.ws_dir / "discovery.json").exists())


class ReopenVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        return cli.main(["lume", *args], start=self.root, clock=self.clock)

    def _ws_dir(self, slug: str) -> Path:
        ws_root = self.root / ".lume" / "workstreams"
        match = next(ws_root.glob(f"*-{slug}"), None)
        return match if match is not None else ws_root / slug

    def _make_closed(self, slug="ws"):
        repo = Repository(self.root, self.clock)
        ws = repo.create_workstream(slug, "Title")
        ws.set_status("closed")
        return self._ws_dir(slug)

    def test_reopen_flips_status_active(self):
        ws_dir = self._make_closed()
        rc = self._run("reopen", "ws")
        self.assertEqual(rc, 0)
        doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
        self.assertEqual(doc["workstream"]["status"], "active")
        obj = json.loads((ws_dir / "objective.json").read_text())
        self.assertEqual(obj["status"], "active")

    def test_reopen_already_active_errors(self):
        Repository(self.root, self.clock).create_workstream("live", "T")
        self.assertEqual(self._run("reopen", "live"), 1)

    def test_reopen_unknown_errors(self):
        self.assertEqual(self._run("reopen", "nope"), 1)

    def test_reopen_missing_arg_usage(self):
        self.assertEqual(self._run("reopen"), 2)


if __name__ == "__main__":
    unittest.main()
