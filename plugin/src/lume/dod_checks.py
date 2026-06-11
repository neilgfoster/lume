"""Evaluate the machine-verifiable checks on an iteration's DoD items.

Pure and side-effect-free at import. `evaluate_dod()` reads a content doc's
`dod.items`, runs each item's optional `check` predicate, and returns a per-item
result. It mutates no state and is reused by the accept veto (P8) and the
`lume check` dry-run verb (P9).

v0.1 supports three predicate kinds (decision, iteration 005):
- command:      a shell command; passes iff it exits 0 (cwd=repo_root, timeout).
- file-exists:  a repo-relative path; passes iff it exists.
- schema-valid: a repo-relative JSON file; passes iff it loads and validates
                against the named lume entity schema.

Per-kind required fields are enforced HERE, not in the schema: the schema
validator is a deliberate subset with no `oneOf`, so a malformed check (missing
`cmd`/`path`/`entity`) fails closed with a reason rather than being rejected at
validation time.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .errors import SchemaError
from .validate import validate_entity

# Default wall-clock budget for a `command` check. A module constant so tests
# can monkeypatch it small; not operator-configurable in v0.1 (decision 005).
COMMAND_TIMEOUT_SECONDS = 120


def evaluate_dod(content_doc: dict, repo_root) -> list[dict]:
    """Per-item check results for a content doc's DoD.

    Each result is {index, text, verifiable, passed, kind, reason}:
    - verifiable=False/passed=None for a prose-only item (no `check`);
    - verifiable=True/passed=bool for an item carrying a `check`.
    Pure: runs the predicates but mutates no state.
    """
    root = Path(repo_root)
    results = []
    items = content_doc.get("dod", {}).get("items", [])
    for index, item in enumerate(items):
        text = item.get("text", "")
        check = item.get("check")
        if check is None:
            results.append({
                "index": index, "text": text,
                "verifiable": False, "passed": None,
                "kind": None, "reason": "no machine check (prose-only)",
            })
            continue
        kind = check.get("kind")
        passed, reason = _evaluate_check(kind, check, root)
        results.append({
            "index": index, "text": text,
            "verifiable": True, "passed": passed,
            "kind": kind, "reason": reason,
        })
    return results


def verifiability_summary(content_doc: dict) -> dict:
    """Static classification of a DoD's items - no predicate is executed.

    Returns {total, verifiable, prose_only, has_command_checks}. Lets a caller
    (e.g. an autonomous operator) judge whether a DoD is fully machine-checkable
    and whether it carries command checks (a code-execution surface) before
    deciding to auto-accept versus escalate.
    """
    items = content_doc.get("dod", {}).get("items", [])
    verifiable = [i for i in items if i.get("check") is not None]
    has_command = any(i["check"].get("kind") == "command" for i in verifiable)
    return {
        "total": len(items),
        "verifiable": len(verifiable),
        "prose_only": len(items) - len(verifiable),
        "has_command_checks": has_command,
    }


def _evaluate_check(kind, check, root: Path):
    if kind == "command":
        cmd = check.get("cmd")
        if not cmd:
            return False, "command check missing 'cmd'"
        return _run_command(cmd, root)
    if kind == "file-exists":
        path = check.get("path")
        if not path:
            return False, "file-exists check missing 'path'"
        if (root / path).exists():
            return True, f"{path} exists"
        return False, f"{path} does not exist"
    if kind == "schema-valid":
        path = check.get("path")
        entity = check.get("entity")
        if not path or not entity:
            return False, "schema-valid check missing 'path' or 'entity'"
        return _validate_file(path, entity, root)
    return False, f"unknown check kind {kind!r}"


def _run_command(cmd: str, root: Path):
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(root),
            capture_output=True, timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {COMMAND_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return False, f"command failed to run: {exc}"
    if proc.returncode == 0:
        return True, "command exited 0"
    return False, f"command exited {proc.returncode}"


def _validate_file(path: str, entity: str, root: Path):
    target = root / path
    if not target.is_file():
        return False, f"{path} does not exist"
    try:
        doc = json.loads(target.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"{path} is not valid JSON: {exc}"
    try:
        validate_entity(entity, doc)
    except SchemaError as exc:
        return False, f"{path} failed {entity} schema: {exc}"
    return True, f"{path} valid against {entity}"
