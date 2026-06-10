"""P12: decisions.json + retro.json as canonical source; .md are derived views."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import cli, migrate, state as state_mod
from lume.clock import FixedClock
from lume.decisions import parse_decisions_md
from lume.retro import parse_retro_md
from lume.validate import validate_entity
from lume.workstream import Workstream


def _initial_doc():
    return {
        "workstream": {
            "slug": "demo", "title": "Demo",
            "status": "active", "objective_artifact": "objective.json",
        },
        "iterations": [],
        "plan": [],
    }


def _make_ws_dir(tmp: str) -> Path:
    ws_dir = Path(tmp) / "demo"
    (ws_dir / "iterations").mkdir(parents=True)
    (ws_dir / "objective.json").write_text(json.dumps(
        {"slug": "demo", "title": "Demo", "status": "active", "text": "obj"},
        indent=2,
    ) + "\n")
    state_mod.save(ws_dir / state_mod.STATE_FILE, _initial_doc())
    return ws_dir


def _ws(ws_dir: Path, clock: FixedClock) -> Workstream:
    return Workstream.on_filesystem(ws_dir, clock, state_mod.load(ws_dir / state_mod.STATE_FILE))


class DecideTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = _make_ws_dir(self._tmp.name)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def test_decide_appends_and_validates(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.add_decision("Use JSON", context="(014 P12)", rationale="schema-validated")
        doc = json.loads((self.ws_dir / "decisions.json").read_text())
        validate_entity("decisions", doc)
        self.assertEqual(len(doc["entries"]), 1)
        self.assertEqual(doc["entries"][0]["decision"], "Use JSON")
        self.assertEqual(doc["entries"][0]["date"], "2026-06-10")

    def test_decide_writes_no_md_view(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.add_decision("Use JSON", context="(014 P12)", rationale="why")
        self.assertFalse((self.ws_dir / "decisions.md").exists())

    def test_decide_appends_to_existing(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.add_decision("First", rationale="r1")
        ws.add_decision("Second", rationale="r2")
        doc = json.loads((self.ws_dir / "decisions.json").read_text())
        self.assertEqual([e["decision"] for e in doc["entries"]], ["First", "Second"])


class DecisionsRoundTripTest(unittest.TestCase):
    def test_parse_legacy_decisions_md(self):
        md = (
            "# demo - decisions\n\nHeader.\n\n"
            "- 2026-06-10 | (002 planning) GO | bounded cost\n"
            "- 2026-06-10 | No context here | still fine\n"
        )
        self.assertEqual(parse_decisions_md(md), [
            {"date": "2026-06-10", "context": "(002 planning)",
             "decision": "GO", "rationale": "bounded cost"},
            {"date": "2026-06-10", "context": "",
             "decision": "No context here", "rationale": "still fine"},
        ])


class RetroTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = _make_ws_dir(self._tmp.name)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_retro_creates_and_validates(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.save_retro({"overall_verdict": "Net positive", "carry_forwards": ["next thing"]})
        doc = json.loads((self.ws_dir / "retro.json").read_text())
        validate_entity("retro", doc)
        self.assertEqual(doc["overall_verdict"], "Net positive")

    def test_save_retro_writes_no_md_view(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.save_retro({"overall_verdict": "Net positive", "carry_forwards": ["next thing"]})
        self.assertFalse((self.ws_dir / "retro.md").exists())

    def test_retro_update_overwrites(self):
        ws = _ws(self.ws_dir, self.clock)
        ws.save_retro({"overall_verdict": "v1", "carry_forwards": []})
        ws.save_retro({"overall_verdict": "v2", "carry_forwards": []})
        doc = json.loads((self.ws_dir / "retro.json").read_text())
        self.assertEqual(doc["overall_verdict"], "v2")


class ParseLegacyRetroTest(unittest.TestCase):
    _LEGACY = (
        "# demo - retro\n\n## Per-stage verdict\n\n"
        "| Stage | Iterations | Cost | Saved | Net |\n|---|---|---|---|---|\n"
        "| Discovery | 002 | one | lots | Positive |\n\n"
        "## Objective done-when\n\n"
        "| Clause | Verdict | Evidence |\n|---|---|---|\n"
        "| Typed iterations | MET | tests |\n\n"
        "## Overall verdict\n\nNet positive\n\n"
        "## Carry-forwards\n\n- next workstream\n\n"
        "## Operator verdict\n\nNet positive lived experience.\n"
    )

    def test_parses_tables_sections_and_fields(self):
        parsed = parse_retro_md(self._LEGACY)
        self.assertEqual(parsed["overall_verdict"], "Net positive")
        self.assertEqual(parsed["carry_forwards"], ["next workstream"])
        self.assertEqual(len(parsed["stage_verdicts"]), 1)
        self.assertEqual(parsed["stage_verdicts"][0]["stage"], "Discovery")
        self.assertEqual(len(parsed["done_when"]), 1)
        self.assertEqual(parsed["sections"][0]["heading"], "Operator verdict")

    def test_step_column_maps_to_stage(self):
        md = (
            "# demo - retro\n\n## Per-step verdict\n\n"
            "| Step | Cost | Saves | Net |\n|---|---|---|---|\n"
            "| 1. Create | small | anchors | Positive |\n\n"
            "## Overall verdict\n\ndone\n"
        )
        parsed = parse_retro_md(md)
        self.assertEqual(parsed["stage_verdicts"][0]["stage"], "1. Create")
        self.assertEqual(parsed["stage_verdicts"][0]["saved"], "anchors")


class MigrateDecisionsRetroTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws_dir = _make_ws_dir(self._tmp.name)
        # objective.md required for migrate_all discovery + build_doc_from_markdown.
        (self.ws_dir / "objective.md").write_text(
            "---\nslug: demo\nstatus: active\n---\n# Demo\n\nobjective\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _doc(self):
        return migrate.build_doc_from_markdown(self.ws_dir)

    def test_migrate_decisions_parses(self):
        (self.ws_dir / "decisions.md").write_text(
            "# demo - decisions\n\nHeader.\n\n"
            "- 2026-06-09 | (002 planning) GO | bounded cost\n"
        )
        migrate.migrate_decisions(self.ws_dir, self._doc())
        doc = json.loads((self.ws_dir / "decisions.json").read_text())
        validate_entity("decisions", doc)
        self.assertEqual(doc["entries"][0]["decision"], "GO")
        self.assertEqual(doc["entries"][0]["context"], "(002 planning)")

    def test_migrate_retro_parses(self):
        (self.ws_dir / "retro.md").write_text(
            "# demo - retro\n\n## Overall verdict\n\nNet positive.\n\n"
            "## Handoff\n\n- do the next thing\n\n## Notes\n\nfreeform prose\n"
        )
        migrate.migrate_retro(self.ws_dir, self._doc())
        doc = json.loads((self.ws_dir / "retro.json").read_text())
        validate_entity("retro", doc)
        self.assertEqual(doc["overall_verdict"], "Net positive.")
        self.assertEqual(doc["carry_forwards"], ["do the next thing"])
        self.assertEqual(doc["sections"][0]["heading"], "Notes")

    def test_migrate_idempotent(self):
        (self.ws_dir / "decisions.md").write_text(
            "# d\n\n- 2026-06-09 | (x) A | r\n"
        )
        (self.ws_dir / "retro.md").write_text(
            "# r\n\n## Overall verdict\n\nv\n\n## Extra\n\nbody\n"
        )
        doc = self._doc()
        migrate.migrate_decisions(self.ws_dir, doc)
        migrate.migrate_retro(self.ws_dir, doc)
        d1 = (self.ws_dir / "decisions.json").read_text()
        r1 = (self.ws_dir / "retro.json").read_text()
        migrate.migrate_decisions(self.ws_dir, doc)
        migrate.migrate_retro(self.ws_dir, doc)
        self.assertEqual((self.ws_dir / "decisions.json").read_text(), d1)
        self.assertEqual((self.ws_dir / "retro.json").read_text(), r1)


class CliDispatchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ws_dir = (root / ".lume" / "workstreams" / "demo")
        self.ws_dir.mkdir(parents=True)
        (self.ws_dir / "iterations").mkdir()
        (self.ws_dir / "objective.json").write_text(json.dumps(
            {"slug": "demo", "title": "Demo", "status": "active", "text": "obj"}) + "\n")
        state_mod.save(self.ws_dir / state_mod.STATE_FILE, _initial_doc())
        self.root = root
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def test_decide_usage_error_without_arg(self):
        rc = cli.main(["lume", "decide"], start=self.root, clock=self.clock)
        self.assertEqual(rc, 2)

    def test_decide_logs_entry(self):
        rc = cli.main(
            ["lume", "-c", "(014)", "decide", "Use JSON", "because"],
            start=self.root, clock=self.clock,
        )
        self.assertEqual(rc, 0)
        doc = json.loads((self.ws_dir / "decisions.json").read_text())
        self.assertEqual(doc["entries"][0]["decision"], "Use JSON")
        self.assertEqual(doc["entries"][0]["context"], "(014)")
        self.assertEqual(doc["entries"][0]["rationale"], "because")

    def test_retro_creates_scaffold(self):
        rc = cli.main(["lume", "retro"], start=self.root, clock=self.clock)
        self.assertEqual(rc, 0)
        self.assertTrue((self.ws_dir / "retro.json").is_file())
        self.assertFalse((self.ws_dir / "retro.md").exists())


if __name__ == "__main__":
    unittest.main()
