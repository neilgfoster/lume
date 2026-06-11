"""pyproject's version must equal lume's version of record (P5/L4, P11).

plugin/.claude-plugin/plugin.json is the single source of truth for lume's
version; pyproject.toml only echoes it. This test fails CI if they drift, so
the pyproject can never quietly become a second source. Uses stdlib tomllib
(Python >= 3.11, lume's floor).
"""
import json
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class VersionConsistencyTest(unittest.TestCase):
    def test_pyproject_version_matches_plugin_json(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        plugin = json.loads(
            (REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(
            pyproject["project"]["version"], plugin["version"],
            "pyproject.toml version must equal plugin.json (the version of record)",
        )


if __name__ == "__main__":
    unittest.main()
