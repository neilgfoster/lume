"""Unit tests for the pure DoD check evaluator (P3/L2 build step 1, P7).

The evaluator is not yet wired into accept (that is P8); these tests exercise
evaluate_dod in isolation across every predicate kind and branch, plus the
back-compat guarantee that a checkless iteration_content still validates.
"""
import json
import tempfile
import unittest
from pathlib import Path

from lume import dod_checks
from lume.dod_checks import evaluate_dod
from lume.validate import validate_entity


def _content(items):
    return {"id": 1, "dod": {"preamble": "", "items": items}, "self_review": None, "handback": None}


class EvaluateDodTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _one(self, item):
        return evaluate_dod(_content([item]), self.root)[0]

    # --- prose-only / non-verifiable -------------------------------------
    def test_prose_only_item_is_non_verifiable(self):
        r = self._one({"text": "subjective", "checked": True})
        self.assertFalse(r["verifiable"])
        self.assertIsNone(r["passed"])
        self.assertIsNone(r["kind"])

    # --- command ----------------------------------------------------------
    def test_command_exit_zero_passes(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "command", "cmd": "true"}})
        self.assertTrue(r["verifiable"])
        self.assertTrue(r["passed"])

    def test_command_nonzero_fails(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "command", "cmd": "false"}})
        self.assertTrue(r["verifiable"])
        self.assertFalse(r["passed"])

    def test_command_not_found_fails(self):
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "command", "cmd": "no_such_cmd_xyz"}})
        self.assertFalse(r["passed"])

    def test_command_timeout_fails(self):
        original = dod_checks.COMMAND_TIMEOUT_SECONDS
        dod_checks.COMMAND_TIMEOUT_SECONDS = 0.2
        try:
            r = self._one({"text": "t", "checked": False,
                           "check": {"kind": "command", "cmd": "sleep 5"}})
        finally:
            dod_checks.COMMAND_TIMEOUT_SECONDS = original
        self.assertFalse(r["passed"])
        self.assertIn("timed out", r["reason"])

    def test_command_missing_cmd_fails_closed(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "command"}})
        self.assertFalse(r["passed"])
        self.assertIn("missing", r["reason"])

    def test_command_runs_in_repo_root(self):
        (self.root / "marker.txt").write_text("x")
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "command", "cmd": "test -f marker.txt"}})
        self.assertTrue(r["passed"])

    # --- file-exists ------------------------------------------------------
    def test_file_exists_hit(self):
        (self.root / "present.txt").write_text("x")
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "file-exists", "path": "present.txt"}})
        self.assertTrue(r["passed"])

    def test_file_exists_miss(self):
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "file-exists", "path": "absent.txt"}})
        self.assertFalse(r["passed"])

    def test_file_exists_missing_path_fails_closed(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "file-exists"}})
        self.assertFalse(r["passed"])
        self.assertIn("missing", r["reason"])

    # --- schema-valid -----------------------------------------------------
    def test_schema_valid_passes(self):
        good = {"slug": "s", "title": "t", "status": "active", "text": "x"}
        (self.root / "obj.json").write_text(json.dumps(good))
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "schema-valid", "entity": "objective", "path": "obj.json"}})
        self.assertTrue(r["passed"])

    def test_schema_valid_invalid_doc_fails(self):
        bad = {"slug": "s"}  # missing required title/status/text
        (self.root / "obj.json").write_text(json.dumps(bad))
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "schema-valid", "entity": "objective", "path": "obj.json"}})
        self.assertFalse(r["passed"])

    def test_schema_valid_missing_file_fails(self):
        r = self._one({"text": "t", "checked": False,
                       "check": {"kind": "schema-valid", "entity": "objective", "path": "gone.json"}})
        self.assertFalse(r["passed"])
        self.assertIn("does not exist", r["reason"])

    def test_schema_valid_missing_fields_fails_closed(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "schema-valid"}})
        self.assertFalse(r["passed"])
        self.assertIn("missing", r["reason"])

    # --- unknown kind -----------------------------------------------------
    def test_unknown_kind_fails_closed(self):
        r = self._one({"text": "t", "checked": False, "check": {"kind": "bogus"}})
        self.assertFalse(r["passed"])

    # --- ordering / multiple ---------------------------------------------
    def test_results_track_item_order(self):
        results = evaluate_dod(_content([
            {"text": "a", "checked": False, "check": {"kind": "command", "cmd": "true"}},
            {"text": "b", "checked": False},
        ]), self.root)
        self.assertEqual([r["index"] for r in results], [0, 1])
        self.assertTrue(results[0]["verifiable"])
        self.assertFalse(results[1]["verifiable"])


class BackCompatTest(unittest.TestCase):
    def test_checkless_content_still_validates(self):
        doc = _content([{"text": "prose item", "checked": True}])
        validate_entity("iteration_content", doc)  # must not raise

    def test_content_with_check_validates(self):
        doc = _content([{"text": "verifiable", "checked": False,
                         "check": {"kind": "file-exists", "path": "x"}}])
        validate_entity("iteration_content", doc)  # must not raise


if __name__ == "__main__":
    unittest.main()
