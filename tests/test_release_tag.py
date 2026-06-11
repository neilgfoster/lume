"""The release-tag checker agrees with the version of record (P5/L4, P13)."""
import json
import unittest
from pathlib import Path

from tools.check_release_tag import check

REPO_ROOT = Path(__file__).resolve().parent.parent


def _version() -> str:
    return json.loads(
        (REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())["version"]


class ReleaseTagTest(unittest.TestCase):
    def test_matching_tag_passes(self):
        ok, _ = check(f"v{_version()}")
        self.assertTrue(ok)

    def test_refs_tags_prefix_accepted(self):
        ok, _ = check(f"refs/tags/v{_version()}")
        self.assertTrue(ok)

    def test_mismatched_tag_fails(self):
        ok, msg = check("v9.9.9")
        self.assertFalse(ok)
        self.assertIn("expected", msg)

    def test_missing_tag_fails(self):
        ok, _ = check(None)
        self.assertFalse(ok)

    def test_tag_without_v_prefix_fails(self):
        ok, _ = check(_version())
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
