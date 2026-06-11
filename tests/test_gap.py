"""gap entity + capture: schema, module helpers, and the CLI add->list flow (P2/L1, P15)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lume.errors import LumeError, SchemaError
from lume.gap import (add_gap, gaps_dir, gaps_for_workstream, link_gap,
                      next_id, read_gaps, resolve_gap)
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

    def test_gaps_live_under_lume_dir(self):
        # Gaps are lume state, co-located with the rest of it under .lume/.
        self.assertEqual(gaps_dir(self.root), self.root / ".lume" / "gaps")

    def test_next_id_sequences(self):
        self.assertEqual(next_id([]), "G1")
        self.assertEqual(next_id([{"id": "G1"}, {"id": "G2"}]), "G3")

    def test_add_writes_valid_file_and_reads_back(self):
        rec = add_gap(self.root, title="Needs X, badly!", source="demo",
                      created="2026-06-11", context="because Y")
        self.assertEqual(rec["id"], "G1")
        self.assertEqual(rec["status"], "open")
        # Workstream-style filename: <source>-<nnnn>-<stub>.json (padded id
        # and slugified title hint in the NAME only; the id stays G<n>).
        on_disk = json.loads(
            (gaps_dir(self.root) / "demo-0001-needs-x-badly.json").read_text())
        self.assertEqual(on_disk, rec)
        self.assertEqual(read_gaps(self.root), [rec])

    def test_legacy_filename_still_read_and_migrates_on_write(self):
        d = gaps_dir(self.root)
        d.mkdir(parents=True)
        legacy = {"id": "G1", "source": "demo", "title": "old name", "context": "",
                  "status": "open", "created": "2026-06-11", "resolution": None}
        (d / "demo-G1.json").write_text(json.dumps(legacy))
        self.assertEqual(read_gaps(self.root), [legacy])  # legacy name readable
        link_gap(self.root, "demo", "G1", "0019")  # any write renames it
        self.assertFalse((d / "demo-G1.json").exists())
        self.assertTrue((d / "demo-0001-old-name.json").exists())
        self.assertEqual(len(read_gaps(self.root)), 1)  # no duplicate

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


class GapLinkageSchemaTest(unittest.TestCase):
    BASE = {"id": "G1", "source": "demo", "title": "t", "context": "",
            "status": "open", "created": "2026-06-11", "resolution": None}

    def test_record_without_new_fields_still_validates(self):
        validate_entity("gap", dict(self.BASE))  # back-compat: both optional

    def test_workstreams_and_structured_resolution_validate(self):
        rec = dict(self.BASE, workstreams=["0018"], status="resolved",
                   resolution={"kind": "implemented", "note": "done",
                               "workstream": "0018"})
        validate_entity("gap", rec)

    def test_bad_resolution_kind_rejected(self):
        rec = dict(self.BASE, resolution={"kind": "maybe-later"})
        with self.assertRaises(SchemaError):
            validate_entity("gap", rec)

    def test_resolution_missing_kind_rejected(self):
        rec = dict(self.BASE, resolution={"note": "no kind"})
        with self.assertRaises(SchemaError):
            validate_entity("gap", rec)


class GapLinkageModuleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        add_gap(self.root, "needs linking", "demo", "2026-06-11")

    def tearDown(self):
        self._tmp.cleanup()

    def test_link_is_idempotent(self):
        link_gap(self.root, "demo", "G1", "0018")
        rec = link_gap(self.root, "demo", "G1", "0018")
        self.assertEqual(rec["workstreams"], ["0018"])

    def test_link_unknown_gap_is_named_error(self):
        with self.assertRaises(LumeError):
            link_gap(self.root, "demo", "G9", "0018")

    def test_resolve_persists_structured_resolution_and_links(self):
        rec = resolve_gap(self.root, "demo", "G1", note="shipped",
                          workstream_id="0018")
        self.assertEqual(rec["status"], "resolved")
        self.assertEqual(rec["resolution"],
                         {"kind": "implemented", "note": "shipped",
                          "workstream": "0018"})
        self.assertEqual(rec["workstreams"], ["0018"])

    def test_resolve_wont_fix_without_workstream(self):
        rec = resolve_gap(self.root, "demo", "G1", kind="wont-fix")
        self.assertEqual(rec["resolution"], {"kind": "wont-fix"})
        self.assertNotIn("workstreams", rec)

    def test_gaps_for_workstream_derived_by_scan(self):
        self.assertEqual(gaps_for_workstream(self.root, "0018"), [])
        link_gap(self.root, "demo", "G1", "0018")
        answered = gaps_for_workstream(self.root, "0018")
        self.assertEqual([r["id"] for r in answered], ["G1"])


class GapLinkageCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".lume" / "workstreams").mkdir(parents=True)
        self._lume("new", "fix-it", "Fix it")
        self._lume("gap", "add", "needs Z")

    def tearDown(self):
        self._tmp.cleanup()

    def _lume(self, *args):
        return subprocess.run([sys.executable, str(LUME), *args],
                              cwd=str(self.repo), capture_output=True, text=True)

    def test_link_then_status_surfaces_gap(self):
        link = self._lume("gap", "link", self.repo.name, "G1", "-w", "fix-it")
        self.assertEqual(link.returncode, 0, link.stderr)
        detail = self._lume("--json", "status", "-w", "fix-it")
        doc = json.loads(detail.stdout)
        self.assertEqual([g["id"] for g in doc["gaps"]], ["G1"])
        human = self._lume("status", "-w", "fix-it")
        self.assertIn("## Gaps answered", human.stdout)
        self.assertIn("G1", human.stdout)

    def test_link_requires_workstream_flag(self):
        out = self._lume("gap", "link", self.repo.name, "G1")
        self.assertEqual(out.returncode, 2)

    def test_link_unknown_workstream_is_error(self):
        out = self._lume("gap", "link", self.repo.name, "G1", "-w", "nope")
        self.assertEqual(out.returncode, 1)

    def test_resolve_persists_note_and_workstream(self):
        res = self._lume("--json", "gap", "resolve", self.repo.name, "G1",
                         "-w", "fix-it", "done and dusted")
        self.assertEqual(res.returncode, 0, res.stderr)
        doc = json.loads(res.stdout)
        self.assertEqual(doc["resolution"]["note"], "done and dusted")
        self.assertEqual(doc["resolution"]["kind"], "implemented")
        listed = json.loads(self._lume("--json", "gap", "list").stdout)
        self.assertEqual(listed[0]["resolution"]["workstream"], "0001")

    def test_resolve_bad_kind_is_usage_error(self):
        out = self._lume("gap", "resolve", self.repo.name, "G1", "-t", "later")
        self.assertEqual(out.returncode, 2)

    def test_plain_resolve_still_works(self):
        res = self._lume("gap", "resolve", self.repo.name, "G1")
        self.assertEqual(res.returncode, 0, res.stderr)
        listed = json.loads(self._lume("--json", "gap", "list").stdout)
        self.assertEqual(listed[0]["status"], "resolved")
        self.assertEqual(listed[0]["resolution"], {"kind": "implemented"})


if __name__ == "__main__":
    unittest.main()
