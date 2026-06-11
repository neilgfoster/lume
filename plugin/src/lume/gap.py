"""Capability-gap records - the cross-repo lume<->adopter integration unit.

A `gap` is a capability gap one repo records about lume: lume writes them about
itself, and adopters write them about lume. They live per-file at a repo ROOT in
`gaps/<id>.json` (deliberately NOT under `.lume/`, so an adopter can add one with
a single-file PR and lume can read them out of any checked-out repo). This module
is pure I/O over that directory; the scan/ingest of adopter gaps is built on top
of it (P16/P17).

The dedupe identity of a gap is the pair (source, id): the same gap re-read from
the same source on a later scan is the same record, not a new one.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .validate import validate_entity

_ID_RE = re.compile(r"^G(\d+)$")


def gaps_dir(repo_root) -> Path:
    """The repo-root gaps/ directory for `repo_root` (not created here)."""
    return Path(repo_root) / "gaps"


def read_gaps(repo_root) -> list[dict]:
    """Every validated gap record under repo_root/gaps/, sorted by id."""
    d = gaps_dir(repo_root)
    if not d.is_dir():
        return []
    records = []
    for path in sorted(d.glob("*.json")):
        record = json.loads(path.read_text())
        validate_entity("gap", record)
        records.append(record)
    return _sorted(records)


def next_id(existing: list[dict]) -> str:
    """The next 'G<n>' id given existing gap records."""
    highest = 0
    for record in existing:
        m = _ID_RE.match(record.get("id", ""))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"G{highest + 1}"


def add_gap(repo_root, title: str, source: str, created: str,
            context: str = "", status: str = "open") -> dict:
    """Write a new gap record to repo_root/gaps/<id>.json and return it."""
    d = gaps_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    record = {
        "id": next_id(read_gaps(repo_root)),
        "source": source,
        "title": title,
        "context": context,
        "status": status,
        "created": created,
        "resolution": None,
    }
    validate_entity("gap", record)
    (d / f"{record['id']}.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def _sorted(records: list[dict]) -> list[dict]:
    """Sort by numeric id where possible, else lexically by id."""
    def key(r):
        m = _ID_RE.match(r.get("id", ""))
        return (0, int(m.group(1))) if m else (1, r.get("id", ""))
    return sorted(records, key=key)
