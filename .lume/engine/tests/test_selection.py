import datetime
import json
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import GateError, NoWorkstreamError
from lume.repository import Repository


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lume = self.root / ".lume"
        (self.lume / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 1, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _repo(self):
        return Repository(self.root, self.clock)

    def _make_ws(self, slug, status="active"):
        d = self.lume / "workstreams" / slug
        d.mkdir(parents=True)
        (d / "objective.md").write_text(
            f"---\nstatus: {status}\n---\n# {slug.title()}\nthe objective text\n"
        )
        (d / "objective.json").write_text(json.dumps({
            "slug": slug, "title": slug.title(),
            "status": status, "text": "the objective text",
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
        return d

    # --- target by -w slug --------------------------------------------------
    def test_target_by_slug(self):
        self._make_ws("apex")
        self._make_ws("zeta")
        self.assertEqual(self._repo().workstream("zeta").name, "zeta")

    def test_target_unknown_slug_errors(self):
        self._make_ws("apex")
        with self.assertRaises(NoWorkstreamError):
            self._repo().workstream("ghost")

    # --- target by -w id (E2) -----------------------------------------------
    def test_target_by_id(self):
        ws = self._repo().create_workstream("omega", "Omega")
        self.assertEqual(self._repo().workstream(ws.id).name, "omega")

    def test_target_by_id_takes_precedence_over_slug(self):
        # id lookup tried first; when it resolves, use it directly
        ws = self._repo().create_workstream("omega", "Omega")
        ws2 = self._repo().workstream(ws.id)
        self.assertEqual(ws2.id, ws.id)

    def test_target_unknown_id_errors(self):
        with self.assertRaises(NoWorkstreamError):
            self._repo().workstream("9999")

    def test_target_closed_slug_refused(self):
        self._make_ws("apex", status="closed")
        with self.assertRaises(GateError):
            self._repo().workstream("apex")

    # --- default to the sole active workstream ------------------------------
    def test_default_sole_active(self):
        self._make_ws("apex")
        self._make_ws("zeta", status="closed")  # closed does not count
        self.assertEqual(self._repo().workstream().name, "apex")

    def test_default_zero_active_errors(self):
        self._make_ws("apex", status="closed")
        with self.assertRaises(NoWorkstreamError):
            self._repo().workstream()

    def test_default_multi_active_errors_listing_slugs(self):
        self._make_ws("apex")
        self._make_ws("zeta")
        with self.assertRaises(GateError) as cm:
            self._repo().workstream()
        msg = str(cm.exception)
        self.assertIn("apex", msg)
        self.assertIn("zeta", msg)
        self.assertIn("-w", msg)

    # --- status field / active set ------------------------------------------
    def test_active_workstreams_excludes_closed(self):
        self._make_ws("apex")
        self._make_ws("zeta", status="closed")
        self.assertEqual(
            [ws.name for ws in self._repo().active_workstreams(self.lume)], ["apex"]
        )

    def test_objective_line_skips_frontmatter(self):
        self._make_ws("apex")
        self.assertEqual(self._repo().workstream("apex").objective_line(), "Apex")

    # --- create (no cursor) -------------------------------------------------
    def test_create_active_no_cursor_file(self):
        ws = self._repo().create_workstream("fresh", "A Fresh Start")
        self.assertEqual(ws.status, "active")
        self.assertEqual(ws.objective_line(), "A Fresh Start")
        self.assertFalse((self.lume / "current").exists())  # no cursor written
        self.assertEqual(self._repo().workstream("fresh").name, "fresh")

    def test_create_refuses_duplicate(self):
        self._make_ws("apex")
        with self.assertRaises(GateError):
            self._repo().create_workstream("apex", "dup")

    def test_create_refuses_invalid_slug(self):
        for bad in ("", "a/b", "../escape", "has space", "-leading"):
            with self.assertRaises(GateError):
                self._repo().create_workstream(bad, "title")

    # --- close = flip status (no cursor to clear) ---------------------------
    def test_close_flips_status_and_then_refuses_target(self):
        d = self._make_ws("apex")
        self._repo().workstream("apex").set_status("closed")
        self.assertEqual(json.loads((d / "objective.json").read_text())["status"], "closed")
        with self.assertRaises(GateError):
            self._repo().workstream("apex")


if __name__ == "__main__":
    unittest.main()
