"""E3: lume seed verb — creates id-0000 seed workstream + discovery iteration."""
import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from lume.cli import main
from lume.clock import FixedClock
from lume.seed import detect_mode, skeleton_for_mode


class SeedModeDetectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_project_is_new(self):
        self.assertEqual(detect_mode(self.root), "new")

    def test_project_with_other_files_is_existing(self):
        (self.root / "README.md").write_text("# hi")
        self.assertEqual(detect_mode(self.root), "existing")

    def test_only_lume_dir_is_new(self):
        self.assertEqual(detect_mode(self.root), "new")

    def test_skeleton_new_has_why_scope(self):
        sk = skeleton_for_mode("new")
        self.assertIn("Why", sk)
        self.assertIn("Scope", sk)
        self.assertIn("Constraints", sk)
        self.assertIn("Done-when", sk)

    def test_skeleton_existing_has_layout_seams(self):
        sk = skeleton_for_mode("existing")
        self.assertIn("Layout", sk)
        self.assertIn("Seams", sk)
        self.assertIn("Languages", sk)


class SeedVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["lume", *args], start=self.root, clock=self.clock)
        return code, out.getvalue()

    def test_seed_creates_id_0000(self):
        code, _ = self._run("seed", "--new")
        self.assertEqual(code, 0)
        ws_root = self.root / ".lume" / "workstreams"
        seed_dirs = list(ws_root.glob("0000-*"))
        self.assertEqual(len(seed_dirs), 1)

    def test_seed_stamps_seed_true_in_state(self):
        self._run("seed", "--new")
        ws_root = self.root / ".lume" / "workstreams"
        seed_dir = next(ws_root.glob("0000-*"))
        state = json.loads((seed_dir / "state.json").read_text())
        self.assertTrue(state["workstream"].get("seed"))

    def test_seed_opens_discovery_iteration(self):
        self._run("seed", "--new")
        ws_root = self.root / ".lume" / "workstreams"
        seed_dir = next(ws_root.glob("0000-*"))
        iter_file = next(seed_dir.glob("iterations/0001-*.json"))
        self.assertTrue(iter_file.exists())
        content = json.loads(iter_file.read_text())
        items_text = " ".join(i["text"] for i in content["dod"]["items"])
        self.assertIn("Why", items_text)

    def test_seed_existing_mode_uses_repo_map_skeleton(self):
        self._run("seed", "--existing")
        ws_root = self.root / ".lume" / "workstreams"
        seed_dir = next(ws_root.glob("0000-*"))
        content = json.loads(next(seed_dir.glob("iterations/0001-*.json")).read_text())
        items_text = " ".join(i["text"] for i in content["dod"]["items"])
        self.assertIn("Layout", items_text)
        self.assertIn("Seams", items_text)

    def test_seed_auto_detects_new(self):
        code, out = self._run("seed")
        self.assertEqual(code, 0)
        self.assertIn("new", out)

    def test_seed_auto_detects_existing(self):
        (self.root / "README.md").write_text("# hi")
        code, out = self._run("seed")
        self.assertEqual(code, 0)
        self.assertIn("existing", out)

    def test_seed_json_output(self):
        code, out = self._run("--json", "seed", "--new")
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertEqual(obj["result"], "seed")
        self.assertEqual(obj["id"], "0000")
        self.assertEqual(obj["workstream"], "seed")
        self.assertEqual(obj["mode"], "new")
        self.assertEqual(obj["iteration"], 1)

    def test_new_and_existing_flags_conflict(self):
        code, _ = self._run("seed", "--new", "--existing")
        self.assertEqual(code, 2)

    def test_seed_slug_is_seed(self):
        self._run("seed", "--new")
        ws_root = self.root / ".lume" / "workstreams"
        self.assertEqual(len(list(ws_root.glob("0000-seed"))), 1)


if __name__ == "__main__":
    unittest.main()
