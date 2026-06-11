"""The accept gate refuses on a failed DoD machine-check (P3/L2 build step 2, P8).

Builds a filesystem-backed workstream, drives it to a handback iteration whose
DoD carries a `check`, and asserts that transition('accept', repo_root=...)
refuses when the check fails and proceeds when it passes. Also covers the
back-compat skip (repo_root=None) and the CLI-level `lume accept` refusal.
"""
import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lume import state as state_mod
from lume.clock import FixedClock
from lume.errors import GateError
from lume.workstream import Workstream


def _ws_at(root: Path, dod_items) -> Workstream:
    """A filesystem workstream 'demo' with one handback iteration carrying dod_items."""
    ws_dir = root / ".lume" / "workstreams" / "demo"
    (ws_dir / "iterations").mkdir(parents=True)
    (ws_dir / "objective.json").write_text(json.dumps(
        {"slug": "demo", "title": "Demo", "status": "active", "text": "x"}))
    entity = {
        "id": 1, "type": "execution", "phase": "handback", "opened": "2026-06-01",
        "title": "veto", "verdicts": [],
        "dod_artifact": "iterations/0001-veto.json",
    }
    state_mod.save(ws_dir / state_mod.STATE_FILE, {
        "workstream": {"slug": "demo", "title": "Demo", "status": "active",
                       "objective_artifact": "objective.json"},
        "iterations": [entity], "plan": [],
    })
    (ws_dir / "iterations" / "0001-veto.json").write_text(json.dumps(
        {"id": 1, "dod": {"preamble": "", "items": dod_items},
         "self_review": None, "handback": None}))
    state_doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
    return Workstream.on_filesystem(ws_dir, FixedClock(datetime.date(2026, 1, 2)), state_doc)


class AcceptVetoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_failing_check_refuses_accept(self):
        ws = _ws_at(self.root, [
            {"text": "must pass", "checked": False,
             "check": {"kind": "command", "cmd": "false"}}])
        with self.assertRaises(GateError) as cm:
            ws.transition("accept", repo_root=self.root)
        self.assertIn("DoD check(s) failed", str(cm.exception))
        # Phase unchanged on disk.
        doc = state_mod.load(self.root / ".lume" / "workstreams" / "demo" / state_mod.STATE_FILE)
        self.assertEqual(doc["iterations"][-1]["phase"], "handback")

    def test_passing_check_accepts(self):
        ws = _ws_at(self.root, [
            {"text": "must pass", "checked": True,
             "check": {"kind": "command", "cmd": "true"}}])
        it = ws.transition("accept", repo_root=self.root)
        self.assertEqual(it.phase, "accepted")

    def test_prose_only_accepts(self):
        ws = _ws_at(self.root, [{"text": "subjective", "checked": True}])
        it = ws.transition("accept", repo_root=self.root)
        self.assertEqual(it.phase, "accepted")

    def test_no_repo_root_skips_evaluation(self):
        # A would-fail check is ignored when repo_root is absent (back-compat).
        ws = _ws_at(self.root, [
            {"text": "skipped", "checked": False,
             "check": {"kind": "command", "cmd": "false"}}])
        it = ws.transition("accept")
        self.assertEqual(it.phase, "accepted")

    def test_file_exists_check_gates(self):
        ws = _ws_at(self.root, [
            {"text": "artifact present", "checked": False,
             "check": {"kind": "file-exists", "path": "missing.txt"}}])
        with self.assertRaises(GateError):
            ws.transition("accept", repo_root=self.root)

    def test_cli_accept_refuses_on_failed_check(self):
        _ws_at(self.root, [
            {"text": "must pass", "checked": False,
             "check": {"kind": "command", "cmd": "false"}}])
        # Run the CLI accept against the repo root; expect non-zero exit.
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "plugin" / "bin" / "lume"),
             "-w", "demo", "accept"],
            cwd=str(self.root), capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DoD check(s) failed", proc.stderr)


if __name__ == "__main__":
    unittest.main()
