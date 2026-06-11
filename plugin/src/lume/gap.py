"""Capability-gap records - the cross-repo lume<->adopter integration unit.

A `gap` is a capability gap one repo records about lume: lume writes them about
itself, and adopters write them about lume. They live per-file under
`.lume/gaps/<id>.json` - co-located with all other lume state. An adopter can
still add one with a single-file PR, and lume can read them out of any
checked-out repo at the same well-known path. This module
is pure I/O over that directory; the scan/ingest of adopter gaps is built on top
of it (P16/P17).

The dedupe identity of a gap is the pair (source, id): the same gap re-read from
the same source on a later scan is the same record, not a new one.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import LumeError
from .validate import validate_entity

_ID_RE = re.compile(r"^G(\d+)$")


def gaps_dir(repo_root) -> Path:
    """The .lume/gaps/ directory for `repo_root` (not created here)."""
    return Path(repo_root) / ".lume" / "gaps"


def read_gaps(repo_root) -> list[dict]:
    """Every validated gap record under repo_root/.lume/gaps/, sorted by id."""
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
    """The next 'G<n>' id given existing gap records (of one source)."""
    highest = 0
    for record in existing:
        m = _ID_RE.match(record.get("id", ""))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"G{highest + 1}"


def _filename(source: str, id: str) -> str:
    """Source-aware filename so one gaps/ store can hold multiple sources."""
    safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "-", source).strip("-") or "src"
    return f"{safe_source}-{id}.json"


def _write(repo_root, record: dict) -> dict:
    validate_entity("gap", record)
    d = gaps_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    (d / _filename(record["source"], record["id"])).write_text(
        json.dumps(record, indent=2) + "\n")
    return record


def find_gap(repo_root, source: str, id: str) -> dict | None:
    """The gap with this (source, id), or None - the dedupe identity."""
    for r in read_gaps(repo_root):
        if r["source"] == source and r["id"] == id:
            return r
    return None


def add_gap(repo_root, title: str, source: str, created: str,
            context: str = "", status: str = "open") -> dict:
    """Write a new self-authored gap (id sequenced within `source`)."""
    same_source = [r for r in read_gaps(repo_root) if r["source"] == source]
    return _write(repo_root, {
        "id": next_id(same_source),
        "source": source,
        "title": title,
        "context": context,
        "status": status,
        "created": created,
        "resolution": None,
    })


def ingest_gap(repo_root, record: dict) -> bool:
    """Write `record` only if its (source, id) is not already present.

    Returns True if added, False if a record with that identity already exists
    (idempotent ingest - never overwrites, so a resolved gap is not reverted).
    """
    if find_gap(repo_root, record["source"], record["id"]) is not None:
        return False
    _write(repo_root, record)
    return True


def set_status(repo_root, source: str, id: str, status: str) -> dict:
    """Move a gap's status (e.g. acknowledged->resolved); returns the record."""
    record = find_gap(repo_root, source, id)
    if record is None:
        raise LumeError(f"no gap {source}/{id} to set status on.")
    record["status"] = status
    return _write(repo_root, record)


def _sorted(records: list[dict]) -> list[dict]:
    """Sort by numeric id where possible, else lexically by id."""
    def key(r):
        m = _ID_RE.match(r.get("id", ""))
        return (0, int(m.group(1))) if m else (1, r.get("id", ""))
    return sorted(records, key=key)
