#!/usr/bin/env python3
"""Validate the CI workflow's shape without a YAML dependency (P5/L4, P12).

lume is stdlib-only, so rather than add pyyaml just to lint one file, this
asserts the load-bearing lines exist in .github/workflows/ci.yml: it triggers
on push and pull_request, runs pytest, and covers the supported python matrix
(3.11-3.13). Exits non-zero with a clear message on the first missing piece, so
it works as a DoD command-check. Not a full YAML parse - a shape guard.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_VERSIONS = ("3.11", "3.12", "3.13")


def main() -> int:
    if not WORKFLOW.is_file():
        print(f"missing workflow: {WORKFLOW}", file=sys.stderr)
        return 1
    text = WORKFLOW.read_text()
    problems = []
    if "push:" not in text:
        problems.append("no 'push:' trigger")
    if "pull_request:" not in text:
        problems.append("no 'pull_request:' trigger")
    if "pytest" not in text:
        problems.append("does not run pytest")
    for v in REQUIRED_VERSIONS:
        if f'"{v}"' not in text and f"'{v}'" not in text:
            problems.append(f"python {v} missing from the matrix")
    if problems:
        print("CI workflow shape check failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("CI workflow shape OK (push + pull_request, pytest, py 3.11-3.13).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
