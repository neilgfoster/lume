import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lume import state as state_mod
from lume.cli import main
from lume.clock import FixedClock


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lume = self.root / ".lume"
        (self.lume / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["lume", *args], start=self.root, clock=self.clock)
        return code, out.getvalue(), err.getvalue()

    def _make_ws(self, slug, status="active"):
        d = self.lume / "workstreams" / slug
        d.mkdir(parents=True)
        (d / "objective.md").write_text(
            f"---\nstatus: {status}\n---\n# {slug.title()}\nobjective\n"
        )
        (d / "objective.json").write_text(json.dumps({
            "slug": slug, "title": slug.title(), "status": status, "text": "objective",
        }, indent=2) + "\n")
        state_mod.save(d / state_mod.STATE_FILE, {
            "workstream": {
                "slug": slug,
                "title": slug.title(),
                "status": status,
                "objective_artifact": "objective.json",
            },
            "iterations": [],
            "plan": [],
        })

    def _iter(self, slug, n, phase):
        d = self.lume / "workstreams" / slug / "iterations"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{n:03d}.md").write_text(
            f"---\nid: {n:03d}\ntype: execution\nphase: {phase}\nopened: 2026-01-02\n---\n"
            f"# Iteration {n:03d} - t\n"
        )
        (d / f"{n:03d}.json").write_text(json.dumps(
            {"id": n, "dod": {"preamble": "", "items": []}, "self_review": None, "handback": None},
            indent=2,
        ) + "\n")
        state_path = self.lume / "workstreams" / slug / state_mod.STATE_FILE
        doc = state_mod.load(state_path)
        doc["iterations"] = [e for e in doc["iterations"] if e["id"] != n]
        doc["iterations"].append({
            "id": n,
            "type": "execution",
            "phase": phase,
            "opened": "2026-01-02",
            "title": "t",
            "verdicts": [],
            "dod_artifact": f"iterations/{n:03d}.json",
        })
        doc["iterations"].sort(key=lambda e: e["id"])
        state_mod.save(state_path, doc)

    # --- -w targeting -------------------------------------------------------
    def test_w_flag_targets_anywhere(self):
        self._make_ws("apex")
        self._make_ws("zeta")
        for args in (("-w", "zeta", "status"), ("status", "-w", "zeta")):
            code, out, _ = self._run(*args)
            self.assertEqual(code, 0, args)
            self.assertIn("# zeta", out)

    def test_w_without_value_errors(self):
        code, _, err = self._run("status", "-w")
        self.assertEqual(code, 2)
        self.assertIn("needs a workstream", err)

    def test_open_multi_active_needs_w(self):
        self._make_ws("apex")
        self._make_ws("zeta")
        code, _, err = self._run("open", "x")
        self.assertEqual(code, 1)
        self.assertIn("apex", err)
        self.assertIn("zeta", err)
        self.assertIn("-w", err)

    # --- queue vs detail ----------------------------------------------------
    def test_status_queue_buckets(self):
        self._make_ws("awaitw")
        self._iter("awaitw", 1, "handback")
        self._make_ws("workw")
        self._iter("workw", 1, "working")
        self._make_ws("emptyw")  # active, no iterations
        self._make_ws("donew", status="closed")
        code, out, _ = self._run("status")
        self.assertEqual(code, 0)
        self.assertIn("# lume - review queue", out)
        self.assertIn("## Awaiting you", out)
        self.assertIn("awaitw  001 execution handback", out)
        self.assertIn("## In progress", out)
        self.assertIn("workw  001 execution working", out)
        self.assertIn("emptyw  (no iterations)", out)
        self.assertIn("## Closed", out)
        self.assertIn("donew", out)

    def test_status_w_is_detail_not_queue(self):
        self._make_ws("apex")
        code, out, _ = self._run("status", "-w", "apex")
        self.assertEqual(code, 0)
        self.assertIn("# apex", out)
        self.assertIn("objective:", out)
        self.assertNotIn("review queue", out)

    # --- new writes no cursor ----------------------------------------------
    def test_new_creates_active_no_cursor(self):
        code, out, _ = self._run("new", "fresh", "A title")
        self.assertEqual(code, 0)
        self.assertIn("created workstream 'fresh'", out)
        self.assertTrue((self.lume / "workstreams" / "fresh" / "objective.md").is_file())
        self.assertFalse((self.lume / "current").exists())

    # --- single-active flows still work with no -w --------------------------
    def test_e2e_single_active_no_w(self):
        self._make_ws("solo")
        self.assertEqual(self._run("open", "First")[0], 0)
        for verb in ("approve", "start", "handback", "accept"):
            self.assertEqual(self._run(verb)[0], 0, verb)
        _, detail, _ = self._run("status", "-w", "solo")
        self.assertIn("accepted", detail)

    # --- iteration type on open (plan P2) -----------------------------------
    def _iter_type(self, slug, n):
        text = (self.lume / "workstreams" / slug / "iterations" / f"{n:03d}.md").read_text()
        for line in text.splitlines():
            if line.startswith("type:"):
                return line.split(":", 1)[1].strip()
        return None

    def test_open_with_type_persists(self):
        self._make_ws("solo")
        code, _, _ = self._run("open", "--type", "discovery", "A discovery iter")
        self.assertEqual(code, 0)
        self.assertEqual(self._iter_type("solo", 1), "discovery")

    def test_open_defaults_to_execution(self):
        self._make_ws("solo")
        self.assertEqual(self._run("open", "No type given")[0], 0)
        self.assertEqual(self._iter_type("solo", 1), "execution")

    def test_open_unknown_type_rejected_no_file(self):
        self._make_ws("solo")
        code, _, err = self._run("open", "-t", "bogus", "Bad")
        self.assertEqual(code, 1)
        self.assertIn("bogus", err)
        self.assertIn("execution", err)  # allowed set listed
        self.assertFalse((self.lume / "workstreams" / "solo" / "iterations" / "001.md").exists())

    def test_type_surfaced_in_detail(self):
        self._make_ws("solo")
        self._run("open", "--type", "planning", "P")
        _, out, _ = self._run("status", "-w", "solo")
        self.assertIn("(planning)", out)

    def test_close_default_then_zero_active(self):
        self._make_ws("solo")
        code, out, _ = self._run("close")
        self.assertEqual(code, 0)
        self.assertIn("closed workstream 'solo'", out)
        # closed target is refused
        self.assertEqual(self._run("status", "-w", "solo")[0], 1)


if __name__ == "__main__":
    unittest.main()
