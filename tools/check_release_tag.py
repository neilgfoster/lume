#!/usr/bin/env python3
"""Assert a release tag matches lume's version of record (P5/L4, P13).

A release tag must be 'v' + the version in plugin/.claude-plugin/plugin.json
(the single source of truth). This guards the release step the same way
test_version_consistency guards pyproject: the tag can never silently disagree
with the shipped version.

Usage:
    python tools/check_release_tag.py v0.1.0      # explicit tag
    GITHUB_REF_NAME=v0.1.0 python tools/check_release_tag.py   # from CI

Accepts a 'refs/tags/' prefix (as GITHUB_REF provides). Stdlib-only; exits 0 on
match, 1 with a clear message otherwise.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json"


def _normalize(tag: str) -> str:
    """Strip a refs/tags/ prefix and surrounding whitespace."""
    tag = tag.strip()
    prefix = "refs/tags/"
    if tag.startswith(prefix):
        tag = tag[len(prefix):]
    return tag


def check(tag: str | None) -> tuple[bool, str]:
    if not tag:
        return False, "no tag given (pass one as an argument or set GITHUB_REF_NAME)"
    tag = _normalize(tag)
    version = json.loads(PLUGIN_JSON.read_text())["version"]
    expected = f"v{version}"
    if tag == expected:
        return True, f"tag {tag} matches plugin.json version {version}"
    return False, f"tag {tag!r} != expected {expected!r} (plugin.json version {version})"


def main(argv: list[str]) -> int:
    tag = argv[1] if len(argv) > 1 else os.environ.get("GITHUB_REF_NAME")
    ok, message = check(tag)
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
