"""lume review (emit): charter discovery, protocol determinism, read-only property (0015 P1+P2)."""
import datetime
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from lume.cli.app import main
from lume.clock import FixedClock
from lume.review import MAX_DOC_FILES, discover_docs

CLOCK = FixedClock(datetime.date(2026, 6, 11))


def _state_repo(root: Path) -> None:
    """A lume repo with one workstream carrying objective, decisions, and a plan."""
    ws = root / ".lume" / "workstreams" / "0001-demo"
    ws.mkdir(parents=True)
    (ws / "state.json").write_text(json.dumps({
        "workstream": {"id": "0001", "slug": "demo", "title": "Demo workstream",
                       "status": "active", "objective_artifact": "objective.json"},
        "iterations": [],
        "plan": [{"id": "P1", "type": "execution", "tag": "committed",
                  "iter": None, "sketch": "build the thing"}],
    }))
    (ws / "objective.json").write_text(json.dumps({
        "slug": "demo", "title": "Demo workstream", "status": "active",
        "text": "Done when the thing exists."}))
    (ws / "decisions.json").write_text(json.dumps({"entries": [
        {"date": "2026-06-10", "context": "shape", "decision": "keep it flat",
         "rationale": "simpler"}]}))


def _docs(root: Path) -> None:
    (root / "README.md").write_text("# Demo\nThe charter of demo.")
    (root / "docs").mkdir()
    (root / "docs" / "vision.md").write_text("Vision: a thing that exists.")


class _EmitBase(unittest.TestCase):
    with_docs = True

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _state_repo(self.root)
        if self.with_docs:
            _docs(self.root)

    def tearDown(self):
        self._tmp.cleanup()


def _run(root: Path, *args) -> tuple[int, str]:
    """Run main() capturing stdout."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["lume", *args], start=root, clock=CLOCK)
    return code, buf.getvalue()


def _tree_digest(root: Path) -> str:
    """Hash of every file path + content under root (the read-only property)."""
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            h.update(path.relative_to(root).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


class EmitProtocolTest(_EmitBase):
    def test_protocol_contains_all_lenses_and_directives(self):
        code, out = _run(self.root, "review")
        self.assertEqual(code, 0)
        for lens in ("goal-fidelity", "honesty", "ecosystem fit",
                     "value / viability", "keystone", "vision coherence",
                     "trust boundaries", "META / self-improvement"):
            self.assertIn(lens, out)
        # Live-lookup directive, not a baked-in list.
        self.assertIn("marketplace", out)
        self.assertIn("look it up now", out)
        self.assertIn("review_gaps", out)
        self.assertIn("lume review ingest", out)
        self.assertIn("automated self-review", out)

    def test_emit_alias_is_identical(self):
        _, bare = _run(self.root, "review")
        _, alias = _run(self.root, "review", "emit")
        self.assertEqual(bare, alias)

    def test_charter_sources_in_protocol(self):
        _, out = _run(self.root, "review")
        self.assertIn("workstream 0001 demo (active): Demo workstream", out)
        self.assertIn("Done when the thing exists.", out)
        self.assertIn("keep it flat", out)  # decisions embedded for dedupe
        self.assertIn("build the thing", out)  # plan embedded for dedupe
        self.assertIn("### README.md", out)
        self.assertIn("### docs/vision.md", out)

    def test_byte_identical_across_runs(self):
        _, first = _run(self.root, "review")
        _, second = _run(self.root, "review")
        self.assertEqual(first, second)

    def test_emit_is_read_only(self):
        before = _tree_digest(self.root)
        code, _ = _run(self.root, "review")
        self.assertEqual(code, 0)
        self.assertEqual(_tree_digest(self.root), before)

    def test_unknown_subcommand_is_usage_error(self):
        code, _ = _run(self.root, "review", "bogus")
        self.assertEqual(code, 2)

    def test_json_shape_and_labels(self):
        code, out = _run(self.root, "--json", "review")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["result"], "review_emit")
        kinds = {s["kind"] for s in doc["charter_sources"]}
        self.assertEqual(kinds, {"lume-state", "discovered-doc"})
        self.assertEqual(len(doc["lenses"]), 8)
        self.assertEqual(doc["result_schema"]["title"], "review_result")
        self.assertEqual(doc["plan"][0]["sketch"], "build the thing")
        self.assertEqual(doc["decisions"][0]["decision"], "keep it flat")
        self.assertIn("# Adversarial self-review protocol", doc["protocol"])

    def test_charter_override_replaces_scan(self):
        (self.root / "MY-CHARTER.txt").write_text("the real charter")
        code, out = _run(self.root, "--json", "review", "--charter", "MY-CHARTER.txt")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        doc_sources = [s for s in doc["charter_sources"] if s["kind"] != "lume-state"]
        self.assertEqual(doc_sources, [{"source": "MY-CHARTER.txt", "kind": "override"}])
        self.assertNotIn("### README.md", doc["protocol"])
        self.assertIn("the real charter", doc["protocol"])


class EmitNoDocsTest(_EmitBase):
    with_docs = False

    def test_degrades_with_thin_coverage_flag(self):
        code, out = _run(self.root, "review")
        self.assertEqual(code, 0)
        self.assertIn("charter doc coverage is thin: 0 file(s) found", out)
        self.assertIn("flag the missing charter documentation as itself a finding", out)
        # Still a usable protocol: lume-state charter + all lenses present.
        self.assertIn("workstream 0001 demo", out)
        self.assertIn("META / self-improvement", out)


class DocScanTest(_EmitBase):
    def test_cap_and_truncation(self):
        for i in range(MAX_DOC_FILES + 3):
            (self.root / f"README.{i:02d}.md").write_text(f"doc {i}")
        paths, dropped, kind = discover_docs(self.root, None)
        self.assertEqual(len(paths), MAX_DOC_FILES)
        self.assertEqual(kind, "discovered-doc")
        self.assertGreaterEqual(dropped, 3)
        _, out = _run(self.root, "review")
        self.assertIn("dropped by the 12-file cap", out)

    def test_large_file_truncated_visibly(self):
        (self.root / "README.md").write_text("x" * 20000)
        _, out = _run(self.root, "review")
        self.assertIn("truncated by lume review at 8192 characters", out)

    def test_excluded_dirs_never_scanned(self):
        (self.root / ".lume" / "SKILL.md").write_text("not charter")
        paths, _, _ = discover_docs(self.root, None)
        self.assertNotIn(Path(".lume/SKILL.md"), paths)


class CatalogTest(unittest.TestCase):
    def test_review_in_verbs(self):
        from lume.cli.catalog import _VERB_NAMES, USAGE
        self.assertIn("review", _VERB_NAMES)
        self.assertIn("review", USAGE)


if __name__ == "__main__":
    unittest.main()


class PreviousReviewFollowUpTest(_EmitBase):
    """G10: emit seeds the protocol with the prior review's queue plan + adoption."""

    def _store_review(self, proposed, decisions):
        d = self.root / ".lume" / "reviews" / "2026-06-10-01"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({
            "title": "Review result - 2026-06-10-01",
            "sections": [
                {"heading": "proposed_workstreams", "body": json.dumps(proposed)},
                {"heading": "direction_decisions", "body": json.dumps(decisions)},
            ]}))

    def test_no_prior_review_emits_without_section(self):
        code, out = _run(self.root, "review")
        self.assertEqual(code, 0)
        self.assertNotIn("Previous review follow-up", out)

    def test_adoption_status_derived_from_state(self):
        self._store_review(
            proposed=[{"slug": "demo", "title": "Already exists"},
                      {"slug": "never-built", "title": "Still pending"}],
            decisions=[{"context": "c", "decision": "keep it flat", "rationale": "r"},
                       {"context": "c2", "decision": "never logged", "rationale": "r2"}])
        code, out = _run(self.root, "review")
        self.assertEqual(code, 0)
        self.assertIn("Previous review follow-up (1 stored review(s), latest 2026-06-10-01)", out)
        self.assertIn("[ADOPTED] workstream (review 2026-06-10-01): demo", out)
        self.assertIn("[UNADOPTED] workstream (review 2026-06-10-01): never-built", out)
        self.assertIn("[ADOPTED] decision (review 2026-06-10-01): keep it flat", out)
        self.assertIn("[UNADOPTED] decision (review 2026-06-10-01): never logged", out)
        self.assertIn("standing finding", out)

    def test_followup_source_labelled_in_json(self):
        self._store_review(proposed=[], decisions=[])
        code, out = _run(self.root, "--json", "review")
        doc = json.loads(out)
        kinds = {s["kind"] for s in doc["charter_sources"]}
        self.assertIn("previous-review", kinds)
