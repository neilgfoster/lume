"""lume review ingest: validation, dated+sequenced capture, queue-plan emission (0015 P3-P5)."""
import contextlib
import datetime
import io
import json
import tempfile
import unittest
from pathlib import Path

from lume.cli.app import main
from lume.clock import FixedClock
from lume.errors import SchemaError
from lume.store import InMemoryStore, SQLiteStore
from lume.validate import validate_entity

CLOCK = FixedClock(datetime.date(2026, 6, 11))

VALID_RESULT = {
    "direction_decisions": [
        {"context": "scope", "decision": "stay small", "rationale": "charter says so"}],
    "proposed_workstreams": [
        {"slug": "fix-drift", "title": "Fix the drift", "serves_goal": "goal-fidelity",
         "objective": "Done when drift is gone.", "critical_path": True,
         "plan_items": [
             {"sketch": "remove dead verb", "type": "slice", "tag": "committed",
              "evidence": "verbs.py:12"},
             {"sketch": "investigate overlap", "type": "spike", "tag": "optional",
              "evidence": "README claim"}]}],
    "review_gaps": [
        {"gap": "no performance lens", "why_missed": "protocol omits it",
         "proposed_change": "add lens 8"}],
    "provenance": {"source": "lume review", "date": "2026-06-11",
                   "note": "automated self-review, not external validation"},
}


def _run(root: Path, *args) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["lume", *args], start=root, clock=CLOCK)
    return code, buf.getvalue()


class _IngestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.result_path = self.root / "result.json"
        self.result_path.write_text(json.dumps(VALID_RESULT))

    def tearDown(self):
        self._tmp.cleanup()


class IngestValidationTest(_IngestBase):
    def test_schema_accepts_valid_result(self):
        validate_entity("review_result", VALID_RESULT)

    def test_schema_rejects_bad_plan_item_type(self):
        bad = json.loads(json.dumps(VALID_RESULT))
        bad["proposed_workstreams"][0]["plan_items"][0]["type"] = "story"
        with self.assertRaises(SchemaError):
            validate_entity("review_result", bad)

    def test_missing_path_is_usage_error(self):
        code, _ = _run(self.root, "review", "ingest")
        self.assertEqual(code, 2)

    def test_missing_file_is_usage_error(self):
        code, _ = _run(self.root, "review", "ingest", "nope.json")
        self.assertEqual(code, 2)

    def test_malformed_json_is_usage_error(self):
        self.result_path.write_text("{not json")
        code, _ = _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 2)

    def test_schema_violation_is_usage_error_not_traceback(self):
        bad = json.loads(json.dumps(VALID_RESULT))
        del bad["provenance"]
        self.result_path.write_text(json.dumps(bad))
        code, _ = _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 2)


class IngestCaptureTest(_IngestBase):
    def test_first_run_writes_dated_01_folder(self):
        code, out = _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 0, out)
        folder = self.root / ".lume" / "reviews" / "2026-06-11-01"
        findings = (folder / "findings.md").read_text()
        self.assertIn("# Review findings - 2026-06-11-01", findings)
        self.assertIn("fix-drift: Fix the drift [critical path]", findings)
        self.assertIn("no performance lens", findings)
        self.assertIn("automated self-review", findings)
        # Structured result persisted via the store seam, discovery-shaped.
        stored = json.loads((folder / "result.json").read_text())
        validate_entity("discovery", stored)
        headings = [s["heading"] for s in stored["sections"]]
        self.assertEqual(headings, ["workstream", "provenance", "direction_decisions",
                                    "proposed_workstreams", "review_gaps"])
        self.assertEqual(stored["sections"][0]["body"], "0001")  # the spawned owner

    def test_second_same_day_run_gets_02_without_clobbering_01(self):
        _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        first = (self.root / ".lume" / "reviews" / "2026-06-11-01" / "findings.md").read_text()
        code, _ = _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 0)
        self.assertTrue((self.root / ".lume" / "reviews" / "2026-06-11-02" / "findings.md").is_file())
        self.assertEqual(
            (self.root / ".lume" / "reviews" / "2026-06-11-01" / "findings.md").read_text(), first)

    def test_ingest_spawns_owner_but_never_proposed_workstreams(self):
        _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        ws_dirs = [p.name for p in (self.root / ".lume" / "workstreams").iterdir()]
        # The spawned OWNER exists; the proposed 'fix-drift' was NOT created.
        self.assertEqual(ws_dirs, ["0001-review-2026-06-11-01"])
        state = json.loads((self.root / ".lume" / "workstreams"
                            / "0001-review-2026-06-11-01" / "state.json").read_text())
        self.assertEqual(state["iterations"], [])  # nothing self-approves
        # review_gaps ARE captured as open records (F3, workstream 0020).
        from lume.gap import read_gaps
        gaps = read_gaps(self.root)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["status"], "open")
        self.assertEqual(gaps[0]["title"], "no performance lens")
        self.assertIn("reviews/2026-06-11-01: missed because protocol omits it",
                      gaps[0]["context"])
        self.assertNotIn("workstreams", gaps[0])  # not auto-linked - triage is the operator's

    def test_reingest_captures_its_own_records_no_dedupe(self):
        _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        from lume.gap import read_gaps
        self.assertEqual(len(read_gaps(self.root)), 2)  # per F3: no rerun dedupe


class IngestOwnershipTest(_IngestBase):
    def test_refused_without_workstream_or_spawn(self):
        code, _ = _run(self.root, "review", "ingest", str(self.result_path))
        self.assertEqual(code, 1)  # gate-class named error, not usage/traceback
        self.assertFalse((self.root / ".lume" / "reviews").exists())  # nothing written

    def test_w_attributes_to_existing_active_workstream(self):
        _run(self.root, "new", "owner-ws", "Owner")
        code, out = _run(self.root, "--json", "review", "ingest",
                         str(self.result_path), "-w", "owner-ws")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc["workstream"], "0001")
        stored = json.loads((self.root / ".lume" / "reviews" / "2026-06-11-01"
                             / "result.json").read_text())
        self.assertEqual(stored["sections"][0],
                         {"heading": "workstream", "body": "0001"})

    def test_unknown_workstream_is_named_error(self):
        code, _ = _run(self.root, "review", "ingest", str(self.result_path),
                       "-w", "nope")
        self.assertEqual(code, 1)


class QueuePlanTest(_IngestBase):
    def test_queue_plan_commands(self):
        code, out = _run(self.root, "--json", "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["result"], "review_ingest")
        self.assertEqual(doc["review"], "2026-06-11-01")
        plan = doc["queue_plan"]
        self.assertEqual(plan[0], 'lume new fix-drift "Fix the drift"')
        # Taxonomy mapping: slice -> execution, spike -> discovery.
        self.assertEqual(plan[1],
                         'lume plan add -w fix-drift -t execution -g committed "remove dead verb"')
        self.assertEqual(plan[2],
                         'lume plan add -w fix-drift -t discovery -g optional "investigate overlap"')
        self.assertEqual(plan[3], 'lume decide -c "scope" "stay small" "charter says so"')
        # review_gaps are NOT in the plan - captured as records at ingest (F3).
        self.assertEqual(len(plan), 4)
        self.assertEqual(doc["captured_gaps"], ["G1"])

    def test_empty_collections_emit_no_commands(self):
        empty = {"direction_decisions": [], "proposed_workstreams": [],
                 "review_gaps": [], "provenance": VALID_RESULT["provenance"]}
        self.result_path.write_text(json.dumps(empty))
        code, out = _run(self.root, "review", "ingest", str(self.result_path), "--spawn")
        self.assertEqual(code, 0)
        self.assertIn("(nothing to queue)", out)
        findings = (self.root / ".lume" / "reviews" / "2026-06-11-01" / "findings.md").read_text()
        self.assertIn("(none - the review judged itself thorough)", findings)


class ReviewStoreSeamTest(unittest.TestCase):
    DOC = {"title": "Review result - 2026-06-11-01",
           "sections": [{"heading": "provenance", "body": "{}"}]}

    def test_inmemory_round_trip(self):
        store = InMemoryStore()
        self.assertIsNone(store.read_review("2026-06-11-01"))
        store.write_review("2026-06-11-01", self.DOC)
        self.assertEqual(store.read_review("2026-06-11-01"), self.DOC)

    def test_sqlite_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "lume.db")
            self.assertIsNone(store.read_review("2026-06-11-01"))
            store.write_review("2026-06-11-01", self.DOC)
            self.assertEqual(store.read_review("2026-06-11-01"), self.DOC)

    def test_invalid_shape_rejected(self):
        store = InMemoryStore()
        with self.assertRaises(SchemaError):
            store.write_review("2026-06-11-01", {"nope": True})


if __name__ == "__main__":
    unittest.main()


class FixesContractTest(_IngestBase):
    """G5: optional 'fixes' list - validated, rendered, queued as one chore bundle."""

    def test_schema_accepts_and_requires_fields(self):
        ok = dict(VALID_RESULT, fixes=[{"description": "d", "evidence": "e",
                                        "suggested_change": "s"}])
        validate_entity("review_result", ok)
        with self.assertRaises(SchemaError):
            validate_entity("review_result",
                            dict(VALID_RESULT, fixes=[{"description": "d"}]))

    def test_fixes_render_and_queue_as_chore_bundle(self):
        doc = dict(VALID_RESULT, fixes=[
            {"description": "fix stale test count", "evidence": "README.md:47",
             "suggested_change": "313 -> 421"}])
        self.result_path.write_text(json.dumps(doc))
        code, out = _run(self.root, "--json", "review", "ingest",
                         str(self.result_path), "--spawn")
        self.assertEqual(code, 0, out)
        plan = json.loads(out)["queue_plan"]
        self.assertIn('lume new review-2026-06-11-01-fixes '
                      '"Small fixes from review 2026-06-11-01"', plan)
        self.assertTrue(any("fix stale test count" in c and "plan add" in c
                            for c in plan))
        findings = (self.root / ".lume" / "reviews" / "2026-06-11-01"
                    / "findings.md").read_text()
        self.assertIn("## Fixes (small direct corrections)", findings)
        self.assertIn("313 -> 421", findings)

    def test_result_without_fixes_unchanged(self):
        code, out = _run(self.root, "--json", "review", "ingest",
                         str(self.result_path), "--spawn")
        self.assertEqual(code, 0)
        plan = json.loads(out)["queue_plan"]
        self.assertFalse(any("fixes" in c for c in plan))
