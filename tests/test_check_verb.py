"""`lume check` dry-run verb + DoD verifiability surface (P3/L2 build step 3, P9).

CLI-level tests drive the real verb via subprocess (exit codes + output); unit
tests cover the static verifiability_summary and the status-detail surface.
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
from lume.dod_checks import verifiability_summary
from lume.cli.io import _detail_data
from lume.workstream import Workstream

_LUME = str(Path(__file__).resolve().parent.parent / "plugin" / "bin" / "lume")


def _ws_at(root: Path, dod_items, phase="working") -> Workstream:
    ws_dir = root / ".lume" / "workstreams" / "demo"
    (ws_dir / "iterations").mkdir(parents=True)
    (ws_dir / "objective.json").write_text(json.dumps(
        {"slug": "demo", "title": "Demo", "status": "active", "text": "x"}))
    entity = {
        "id": 1, "type": "execution", "phase": phase, "opened": "2026-06-01",
        "title": "chk", "verdicts": [], "dod_artifact": "iterations/0001-chk.json",
    }
    state_mod.save(ws_dir / state_mod.STATE_FILE, {
        "workstream": {"slug": "demo", "title": "Demo", "status": "active",
                       "objective_artifact": "objective.json"},
        "iterations": [entity], "plan": [],
    })
    (ws_dir / "iterations" / "0001-chk.json").write_text(json.dumps(
        {"id": 1, "dod": {"preamble": "", "items": dod_items},
         "self_review": None, "handback": None}))
    doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
    return Workstream.on_filesystem(ws_dir, FixedClock(datetime.date(2026, 1, 2)), doc)


def _run_check(root: Path, json_mode=False):
    argv = [sys.executable, _LUME] + (["--json"] if json_mode else []) + ["-w", "demo", "check"]
    return subprocess.run(argv, cwd=str(root), capture_output=True, text=True)


class CheckVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_pass_exits_zero(self):
        _ws_at(self.root, [{"text": "ok", "checked": True,
                            "check": {"kind": "command", "cmd": "true"}}])
        proc = _run_check(self.root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PASS", proc.stdout)

    def test_failing_check_exits_nonzero(self):
        _ws_at(self.root, [{"text": "bad", "checked": False,
                            "check": {"kind": "command", "cmd": "false"}}])
        proc = _run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("FAIL", proc.stdout)

    def test_prose_only_exits_zero(self):
        _ws_at(self.root, [{"text": "subjective", "checked": True}])
        proc = _run_check(self.root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("prose", proc.stdout)

    def test_json_shape(self):
        _ws_at(self.root, [
            {"text": "a", "checked": True, "check": {"kind": "command", "cmd": "true"}},
            {"text": "b", "checked": False, "check": {"kind": "command", "cmd": "false"}},
        ])
        proc = _run_check(self.root, json_mode=True)
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["iteration"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(len(payload["results"]), 2)


class VerifiabilitySummaryTest(unittest.TestCase):
    def _summary(self, items):
        return verifiability_summary({"dod": {"items": items}})

    def test_counts_and_command_flag(self):
        s = self._summary([
            {"text": "a", "checked": False, "check": {"kind": "command", "cmd": "true"}},
            {"text": "b", "checked": False, "check": {"kind": "file-exists", "path": "x"}},
            {"text": "c", "checked": True},
        ])
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["verifiable"], 2)
        self.assertEqual(s["prose_only"], 1)
        self.assertTrue(s["has_command_checks"])

    def test_no_command_checks(self):
        s = self._summary([{"text": "b", "checked": False,
                            "check": {"kind": "file-exists", "path": "x"}}])
        self.assertFalse(s["has_command_checks"])


class DetailSurfaceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_detail_data_carries_verifiability(self):
        ws = _ws_at(self.root, [{"text": "a", "checked": False,
                                 "check": {"kind": "command", "cmd": "true"}}])
        data = _detail_data(ws)
        self.assertIn("dod_verifiability", data)
        self.assertEqual(data["dod_verifiability"]["verifiable"], 1)


if __name__ == "__main__":
    unittest.main()
