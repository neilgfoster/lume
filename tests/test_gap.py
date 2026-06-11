"""gap entity + capture: schema, module helpers, and the CLI add->list flow (P2/L1, P15)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lume.errors import SchemaError
from lume.gap import add_gap, gaps_dir, next_id, read_gaps
from lume.validate import validate_entity

REPO_ROOT = Path(__file__).resolve().parent.parent
LUME = REPO_ROOT / "plugin" / "bin" / "lume"


class GapSchemaTest(unittest.TestCase):
    def test_valid_record(self):
        validate_entity("gap", {
            "id": "G1", "source": "demo", "title": "t", "context": "",
            "status": "open", "created": "2026-06-11", "resolution": None})

    def test_bad_status_rejected(self):
        with self.assertRaises(SchemaError):
            validate_entity("gap", {
                "id": "G1", "source": "demo", "title": "t",
                "status": "bogus", "created": "2026-06-11"})


class GapModuleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_next_id_sequences(self):
        self.assertEqual(next_id([]), "G1")
        self.assertEqual(next_id([{"id": "G1"}, {"id": "G2"}]), "G3")

    def test_add_writes_valid_file_and_reads_back(self):
        rec = add_gap(self.root, title="needs X", source="demo",
                      created="2026-06-11", context="because Y")
        self.assertEqual(rec["id"], "G1")
        self.assertEqual(rec["status"], "open")
        # Source-aware filename so one store can hold multiple sources.
        on_disk = json.loads((gaps_dir(self.root) / "demo-G1.json").read_text())
        self.assertEqual(on_disk, rec)
        self.assertEqual(read_gaps(self.root), [rec])

    def test_read_gaps_sorted_and_empty(self):
        self.assertEqual(read_gaps(self.root), [])
        add_gap(self.root, "a", "demo", "2026-06-11")
        add_gap(self.root, "b", "demo", "2026-06-11")
        ids = [r["id"] for r in read_gaps(self.root)]
        self.assertEqual(ids, ["G1", "G2"])


class GapCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".lume" / "workstreams").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _lume(self, *args):
        return subprocess.run([sys.executable, str(LUME), *args],
                              cwd=str(self.repo), capture_output=True, text=True)

    def test_add_then_list(self):
        add = self._lume("gap", "add", "the loop needs Z")
        self.assertEqual(add.returncode, 0, add.stderr)
        self.assertIn("G1", add.stdout)
        listed = self._lume("--json", "gap", "list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        records = json.loads(listed.stdout)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "the loop needs Z")
        self.assertEqual(records[0]["source"], self.repo.name)


if __name__ == "__main__":
    unittest.main()
