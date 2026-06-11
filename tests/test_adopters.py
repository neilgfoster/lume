"""Adopters source of truth + git reach (P2/L1, P16)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from lume.adopters import adopter_cache_root, read_adopters, reach_gaps
from lume.errors import LumeError

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_adopter_repo(path: Path) -> None:
    """A real git repo with one gap committed on its default branch."""
    path.mkdir(parents=True)
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "t@example.com"], path)
    _git(["config", "user.name", "t"], path)
    (path / "gaps").mkdir()
    (path / "gaps" / "G1.json").write_text(json.dumps({
        "id": "G1", "source": "adopter", "title": "needs a thing",
        "context": "", "status": "open", "created": "2026-06-11",
        "resolution": None}))
    _git(["add", "."], path)
    _git(["commit", "-m", "add gap"], path)


class ReadAdoptersTest(unittest.TestCase):
    def test_reads_real_adopters_json(self):
        rows = read_adopters(REPO_ROOT)
        names = {r["project"] for r in rows}
        self.assertIn("lume", names)
        self.assertIn("tredl", names)
        for r in rows:
            self.assertTrue(r["url"].startswith("http"))


class ReachGapsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.adopter = self.base / "adopter-repo"
        _make_adopter_repo(self.adopter)
        self.cache = self.base / "cache"

    def tearDown(self):
        self._tmp.cleanup()

    def test_reach_reads_gap_and_prunes_worktree(self):
        gaps = reach_gaps(str(self.adopter), "adopter", self.cache)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["title"], "needs a thing")
        # No leftover worktree dir, and the clone's worktree list is clean.
        self.assertFalse((self.cache / "adopter.wt").exists())
        wt = subprocess.run(["git", "worktree", "list"], cwd=str(self.cache / "adopter"),
                            capture_output=True, text=True)
        self.assertNotIn(".wt", wt.stdout)

    def test_second_reach_fetches_cached_clone(self):
        reach_gaps(str(self.adopter), "adopter", self.cache)
        # Clone now cached; a second call must still succeed (fetch path).
        gaps = reach_gaps(str(self.adopter), "adopter", self.cache)
        self.assertEqual(len(gaps), 1)

    def test_missing_repo_raises(self):
        with self.assertRaises(LumeError):
            reach_gaps(str(self.base / "does-not-exist"), "ghost", self.cache)

    def test_cache_root_under_lume(self):
        self.assertEqual(adopter_cache_root("/x").as_posix(), "/x/.lume/cache/adopters")


if __name__ == "__main__":
    unittest.main()
