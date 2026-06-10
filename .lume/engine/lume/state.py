"""Per-workstream state.json: the validated, machine-owned source of truth.

One state.json per workstream (decision (a)) holds the workstream record plus
its iterations and plan items:

    {"workstream": {...}, "iterations": [{...}], "plan": [{...}]}

Every entity is validated against its P1 schema on both load and save, so
invalid state never reaches disk and a corrupt file fails loudly at the boundary
rather than surfacing downstream. This module is pure I/O + validation; it does
not know the verbs (P4 rewires the mutating verbs onto it).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import validate
from .errors import LumeError

STATE_FILE = "state.json"


def validate_doc(doc: object) -> None:
    """Validate a whole state document: workstream + each iteration + each plan item.

    Decoupled from path I/O so any backing (filesystem, SQLite, ...) can validate
    a state document without touching files.
    """
    if not isinstance(doc, dict):
        raise LumeError(f"state must be an object, got {type(doc).__name__}.")
    for key in ("workstream", "iterations", "plan"):
        if key not in doc:
            raise LumeError(f"state missing required '{key}'.")
    for key in ("iterations", "plan"):
        if not isinstance(doc[key], list):
            raise LumeError(f"state '{key}' must be an array.")
    validate.validate_entity("workstream", doc["workstream"])
    for item in doc["iterations"]:
        validate.validate_entity("iteration", item)
    for item in doc["plan"]:
        validate.validate_entity("plan_item", item)


def dumps(doc: dict) -> str:
    """Deterministic, diff-friendly serialization: indent=2, sorted keys, trailing newline."""
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def load(path: Path) -> dict:
    """Read + validate the state.json at `path`.

    A missing file, malformed JSON, or a schema failure each raise a named error.
    """
    if not path.is_file():
        raise LumeError(f"no state at {path}.")
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise LumeError(f"malformed state at {path}: {exc}.") from exc
    validate_doc(doc)
    return doc


def save(path: Path, doc: dict) -> None:
    """Validate every entity, then write. Invalid input never reaches disk."""
    validate_doc(doc)
    path.write_text(dumps(doc))
