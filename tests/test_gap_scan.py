"""Contract test: lume gap scan ingests adopter gaps idempotently (P2/L1, P17)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from lume import gap
from lume.adopters import scan_and_ingest

ROOT = Path(__file__).resolve().parent.parent


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _adopter_repo(path: Path) -> None:
    """A git repo with one OPEN and one RESOLVED gap on its default branch."""
    path.mkdir(parents=True)
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "t@e.com"], path)
    _git(["config", "user.name", "t"], path)
    (path / ".lume" / "gaps").mkdir(parents=True)
    (path / ".lume" / "gaps" / "tredl-G1.json").write_text(json.dumps({
        "id": "G1", "source": "tredl", "title": "open gap", "context": "",
        "status": "open", "created": "2026-06-11", "resolution": None}))
    (path / ".lume" / "gaps" / "tredl-G2.json").write_text(json.dumps({
        "id": "G2", "source": "tredl", "title": "resolved gap", "context": "",
        "status": "resolved", "created": "2026-06-11",
        "resolution": {"kind": "implemented", "note": "done"}}))
    _git(["add", "."], path)
    _git(["commit", "-m", "gaps"], path)


def _lume_repo(base: Path, adopter_url: str) -> Path:
    """A temp lume-side repo with .lume/ and ADOPTERS.json pointing at the adopter."""
    repo = base / "lume"
    (repo / ".lume" / "workstreams").mkdir(parents=True)
    (repo / "ADOPTERS.json").write_text(json.dumps({"adopters": [
        {"project": "tredl", "adopter": "t", "url": adopter_url, "since": "2026-06"},
        {"project": "ghost", "adopter": "t", "url": str(base / "missing"), "since": "2026-06"},
    ]}))
    return repo


class GapScanContractTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.adopter = self.base / "tredl"
        _adopter_repo(self.adopter)
        self.repo = _lume_repo(self.base, str(self.adopter))

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_ingests_only_open_and_is_idempotent(self):
        report = scan_and_ingest(self.repo)
        self.assertEqual([k["id"] for k in report["ingested"]], ["G1"])  # open only
        self.assertEqual(len(report["failed"]), 1)  # 'ghost' unreachable, skipped
        ingested = gap.find_gap(self.repo, "tredl", "G1")
        self.assertEqual(ingested["status"], "acknowledged")
        self.assertIsNone(gap.find_gap(self.repo, "tredl", "G2"))  # resolved not ingested

        # Second scan: nothing new.
        report2 = scan_and_ingest(self.repo)
        self.assertEqual(report2["ingested"], [])
        self.assertEqual(len(report2["already_present"]), 1)

    def test_resolve_sticks_across_rescan(self):
        scan_and_ingest(self.repo)
        gap.set_status(self.repo, "tredl", "G1", "resolved")
        scan_and_ingest(self.repo)  # must NOT revert acknowledged
        self.assertEqual(gap.find_gap(self.repo, "tredl", "G1")["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
