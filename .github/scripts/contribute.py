#!/usr/bin/env python3
"""contribute.py — privacy scrub and semver classifier for Hedl self-improvement PRs.

Used by the /contribute flow to validate that a proposed change:
  1. Only touches files under skill/hedl/ (privacy fail-closed scrub).
  2. Is correctly classified for Hedl's own semver bump (deterministic lookup).

The actual `gh pr create` step is NOT performed here — it is performed by
the operator via the /contribute command after explicit confirmation.

Usage:
  contribute.py scrub [--diff-files FILE1 FILE2 ...]
  contribute.py classify --change-type TYPE
  contribute.py --schema
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

FRAMEWORK_PREFIX: str = "skill/hedl/"

# Deterministic classification table derived from the compatibility contract
# (docs/versioning.md).  Keys match the --change-type argument.
MAJOR_SIGNALS: frozenset[str] = frozenset({
    "hedl-toml-schema-break",
    "work-state-schema-break",
    "gate-exit-code-change",
    "tier-layout-break",
    "command-removed",
    "agent-removed",
})

MINOR_SIGNALS: frozenset[str] = frozenset({
    "new-reviewer",
    "new-tier",
    "new-check",
    "new-optional-config",
    "new-command",
})

CLI_SPEC: dict[str, Any] = {
    "name": "contribute",
    "script": "contribute.py",
    "description": "Privacy scrub and semver classifier for Hedl self-improvement PRs.",
    "invocation": "python3 .github/scripts/contribute.py",
    "commands": [
        {
            "name": "scrub",
            "description": "Verify diff only touches skill/hedl/ framework files",
            "args": [
                {
                    "flag": "--diff-files",
                    "type": "str",
                    "required": False,
                    "help": "Space-separated list of changed files (from git diff --name-only)",
                },
            ],
            "output": (
                "Exits 0 if clean (all files under skill/hedl/). "
                "Exits 1 with a list of violations if any non-framework file is present."
            ),
        },
        {
            "name": "classify",
            "description": "Classify a change type against the Hedl semver contract",
            "args": [
                {
                    "flag": "--change-type",
                    "type": "str",
                    "required": True,
                    "help": (
                        f"Change type signal. Major: {sorted(MAJOR_SIGNALS)}. "
                        f"Minor: {sorted(MINOR_SIGNALS)}. All others: patch."
                    ),
                },
            ],
            "output": "JSON with keys: change_type, bump (major|minor|patch).",
        },
    ],
}


def scrub_diff(diff_files: list[str]) -> tuple[bool, list[str]]:
    """Return (is_clean, violations). Fail-closed: any non-framework file is a violation."""
    violations = [f for f in diff_files if not f.startswith(FRAMEWORK_PREFIX)]
    return not violations, violations


def classify_change(change_type: str) -> str:
    """Return 'major', 'minor', or 'patch' for a given change type signal."""
    if change_type in MAJOR_SIGNALS:
        return "major"
    if change_type in MINOR_SIGNALS:
        return "minor"
    return "patch"


def _cmd_scrub(args: argparse.Namespace) -> int:
    files: list[str] = args.diff_files if args.diff_files else []
    clean, violations = scrub_diff(files)
    if clean:
        print(json.dumps({"clean": True, "violations": []}))
        return 0
    result = {
        "clean": False,
        "violations": violations,
        "message": (
            f"{len(violations)} file(s) outside skill/hedl/ — "
            "contribution must only touch Hedl framework files."
        ),
    }
    print(json.dumps(result, indent=2))
    return 1


def _cmd_classify(args: argparse.Namespace) -> int:
    bump = classify_change(args.change_type)
    print(json.dumps({"change_type": args.change_type, "bump": bump}))
    return 0


def main() -> int:
    if "--schema" in sys.argv:
        print(json.dumps(CLI_SPEC, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Hedl contribution helper")
    sub = parser.add_subparsers(dest="cmd")

    scrub_p = sub.add_parser("scrub", help="Privacy scrub diff files")
    scrub_p.add_argument("--diff-files", nargs="*", default=[],
                         help="Changed file paths (from git diff --name-only)")

    classify_p = sub.add_parser("classify", help="Classify change type for semver bump")
    classify_p.add_argument("--change-type", required=True, help="Change type signal")

    args = parser.parse_args()

    if args.cmd == "scrub":
        return _cmd_scrub(args)
    if args.cmd == "classify":
        return _cmd_classify(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
