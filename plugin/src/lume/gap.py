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


_STUB_MAX = 40


def _stub(title: str) -> str:
    """A slugified, length-capped hint from the title for the filename."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:_STUB_MAX].rstrip("-") or "gap"


def _filename(source: str, id: str, title: str = "") -> str:
    """Source-aware filename: <source>-<nnnn>-<stub>.json.

    Follows the workstream NNNN-<slug> convention so files sort sequentially
    per source and carry a readable hint. No 'G' in the name - living under
    .lume/gaps/ already says it's a gap. The padding and stub live in the
    FILENAME only - the gap id stays 'G<n>' and (source, id) remains the
    dedupe identity.
    """
    safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "-", source).strip("-") or "src"
    m = _ID_RE.match(id)
    padded = f"{int(m.group(1)):04d}" if m else id
    return f"{safe_source}-{padded}-{_stub(title)}.json"


def _write(repo_root, record: dict) -> dict:
    validate_entity("gap", record)
    d = gaps_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / _filename(record["source"], record["id"], record.get("title", ""))
    # Rename-on-write: a record still sitting at a legacy name migrates here,
    # so an update never leaves two files for one (source, id).
    for old in d.glob("*.json"):
        if old != path:
            try:
                doc = json.loads(old.read_text())
            except ValueError:
                continue
            if doc.get("source") == record["source"] and doc.get("id") == record["id"]:
                old.unlink()
    path.write_text(json.dumps(record, indent=2) + "\n")
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


def link_gap(repo_root, source: str, id: str, workstream_id: str) -> dict:
    """Record that `workstream_id` answers this gap (idempotent append)."""
    record = find_gap(repo_root, source, id)
    if record is None:
        raise LumeError(f"no gap {source}/{id} to link.")
    linked = record.setdefault("workstreams", [])
    if workstream_id not in linked:
        linked.append(workstream_id)
    return _write(repo_root, record)


def resolve_gap(repo_root, source: str, id: str, kind: str = "implemented",
                note: str = "", workstream_id: str | None = None) -> dict:
    """Resolve a gap with a structured resolution; returns the record.

    Also links `workstream_id` (when given) so the answering workstream is
    data, not prose.
    """
    record = find_gap(repo_root, source, id)
    if record is None:
        raise LumeError(f"no gap {source}/{id} to resolve.")
    resolution: dict = {"kind": kind}
    if note:
        resolution["note"] = note
    if workstream_id:
        resolution["workstream"] = workstream_id
        linked = record.setdefault("workstreams", [])
        if workstream_id not in linked:
            linked.append(workstream_id)
    record["status"] = "resolved"
    record["resolution"] = resolution
    return _write(repo_root, record)


def gaps_for_workstream(repo_root, workstream_id: str) -> list[dict]:
    """The gaps whose `workstreams` list includes this id (derived by scan)."""
    return [r for r in read_gaps(repo_root)
            if workstream_id in r.get("workstreams", [])]


def _sorted(records: list[dict]) -> list[dict]:
    """Sort by numeric id where possible, else lexically by id."""
    def key(r):
        m = _ID_RE.match(r.get("id", ""))
        return (0, int(m.group(1))) if m else (1, r.get("id", ""))
    return sorted(records, key=key)
