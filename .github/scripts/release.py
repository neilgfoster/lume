#!/usr/bin/env python3
"""release.py — deterministic consumer project version bump calculator.

Reads completed work items from .work/work.json for a given phase and computes
the suggested semver bump based on change_class fields.  The bump is always
deterministic; the LLM only writes the prose descriptions in release notes.

Usage:
  release.py --work-json .work/work.json --phase 1
  release.py --work-json .work/work.json --phase 1 --current-version 0.3.0
  release.py --schema   (machine-readable CLI spec)

--current-version must be a canonical X.Y.Z (three dot-separated non-negative
integers; no 'v' prefix, pre-release, or build metadata). Non-canonical input
yields a JSON error envelope ({"error": ...}) and a non-zero exit, never a
traceback.

Output (JSON):
  {
    "phase": 1,
    "current_version": "0.3.0",
    "bump": "minor",
    "proposed_version": "0.4.0",
    "groups": {
      "feat":  [{"id": "WORK-1", "title": "...", "change_class": "feat"}],
      "fix":   [...],
      "chore": [...],
      ...
    }
  }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

CHANGE_CLASSES: frozenset[str] = frozenset({"feat", "fix", "breaking", "chore", "docs"})
DEFAULT_CHANGE_CLASS: str = "chore"

CLI_SPEC: dict[str, Any] = {
    "name": "release",
    "script": "release.py",
    "description": (
        "Compute a deterministic semver bump and release-notes grouping "
        "from completed work-item change_class fields."
    ),
    "invocation": "python3 .github/scripts/release.py",
    "commands": [
        {
            "name": "default",
            "description": "Compute bump and group items for a phase",
            "args": [
                {
                    "flag": "--work-json",
                    "type": "str",
                    "required": True,
                    "help": "Path to .work/work.json",
                },
                {
                    "flag": "--phase",
                    "type": "int",
                    "required": True,
                    "help": "Phase number to compute bump for",
                },
                {
                    "flag": "--current-version",
                    "type": "str",
                    "required": False,
                    "help": "Current project version (X.Y.Z); defaults to 0.0.0",
                },
            ],
            "output": (
                "JSON with keys: phase, current_version, bump, proposed_version, groups. "
                "Exits 0 on success, 1 on error."
            ),
        },
    ],
}


def compute_bump(completed_items: list[dict[str, Any]]) -> str:
    """Determine the semver bump from a list of completed work items.

    Precedence: breaking > feat > everything else (patch).
    """
    classes = {item.get("change_class", DEFAULT_CHANGE_CLASS) for item in completed_items}
    if "breaking" in classes:
        return "major"
    if "feat" in classes:
        return "minor"
    return "patch"


# Supported version grammar: a canonical semver CORE only — exactly three
# dot-separated non-negative integers (X.Y.Z) with no leading zeros. No 'v'
# prefix, pre-release, or build metadata; that matches release.py's stated
# contract (see module docstring) and the consumer version axis.
# `\Z` (not `$`) anchors the true end of string so a trailing newline cannot
# sneak through; re.ASCII keeps `\d` to 0-9 (not Unicode digits).
_NUM = r"(0|[1-9]\d*)"
_VERSION_RE = re.compile(rf"^{_NUM}\.{_NUM}\.{_NUM}\Z", re.ASCII)


def _parse_version(current: str) -> tuple[int, int, int]:
    """Parse a canonical X.Y.Z version into (major, minor, patch).

    Raises ValueError with an actionable message on any non-canonical input
    (e.g. ``1.2``, ``v1.2.3``, ``1.2.3-rc1``, ``""``)."""
    m = _VERSION_RE.match(current)
    if not m:
        raise ValueError(
            f"--current-version {current!r} is not a canonical X.Y.Z version "
            "(three dot-separated non-negative integers, no leading zeros, "
            "e.g. 1.4.2; no 'v' prefix, pre-release, or build metadata)"
        )
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def next_version(current: str, bump: str) -> str:
    """Increment the X.Y.Z version string according to bump type."""
    major, minor, patch = _parse_version(current)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown bump {bump!r} (expected major, minor, or patch)")


def group_by_class(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Return items grouped by change_class, preserving display order. Empty groups omitted."""
    _ORDER = ["breaking", "feat", "fix", "chore", "docs"]
    buckets: dict[str, list[dict[str, Any]]] = {c: [] for c in _ORDER}
    for item in items:
        cls = item.get("change_class", DEFAULT_CHANGE_CLASS)
        buckets.setdefault(cls, []).append(item)
    return {k: buckets[k] for k in _ORDER if buckets.get(k)}


def _load_phase_completed(work_json_path: str, phase: int) -> list[dict[str, Any]]:
    with open(work_json_path, encoding="utf-8") as fh:
        work = json.load(fh)
    items: list[dict[str, Any]] = []
    for item in work.get("completed", []):
        if item.get("phase") == phase:
            items.append(item)
    return items


def main() -> int:
    if "--schema" in sys.argv:
        print(json.dumps(CLI_SPEC, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Deterministic semver bump calculator")
    parser.add_argument("--work-json", required=True, help="Path to .work/work.json")
    parser.add_argument("--phase", type=int, required=True, help="Phase number")
    parser.add_argument("--current-version", default="0.0.0", help="Current X.Y.Z version")
    args = parser.parse_args()

    try:
        _parse_version(args.current_version)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    try:
        items = _load_phase_completed(args.work_json, args.phase)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    bump = compute_bump(items)
    proposed = next_version(args.current_version, bump)
    groups = group_by_class(items)

    result = {
        "phase": args.phase,
        "current_version": args.current_version,
        "bump": bump,
        "proposed_version": proposed,
        "groups": groups,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
