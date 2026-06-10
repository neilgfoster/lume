"""The Tracking contract (scope.md): persistence of workstream/PM state.

A `TrackingStore` is the seam behind which a workstream's artifacts live. It is
a key/value of JSON documents addressed by (slug, artifact), plus workstream
listing/creation. The engine's models and verbs talk to this contract, never to
files directly - so a second backing (SQLite, GitHub Issues, ...) swaps in
without touching anything above it. `Repository` is the policy/resolution layer
that *uses* a store; `FilesystemStore` is its v1 implementation.

Artifact ids (the second key):
    "state" | "objective" | "decisions" | "retro" | "discovery"
    "iteration:NNN"   (NNN zero-padded, e.g. "iteration:003")

`read` returns the parsed JSON document or None when the artifact is absent.
`write` persists a document. The `state` artifact is validated by state.py on
both read and write; other artifacts are validated by their callers (the models)
until E2 moves that responsibility, so the store stays a thin JSON key/value.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Protocol

from . import state as state_mod

WORKSTREAMS_SUBDIR = "workstreams"

# Artifact ids that map to a top-level <name>.json in the workstream dir.
_SIMPLE_ARTIFACTS = ("objective", "decisions", "retro", "discovery")


class TrackingStore(Protocol):
    def list_workstreams(self) -> list[str]: ...
    def has_workstream(self, slug: str) -> bool: ...
    def create_workstream(self, slug: str) -> None: ...
    def read(self, slug: str, artifact: str) -> dict | None: ...
    def write(self, slug: str, artifact: str, doc: dict) -> None: ...


class FilesystemStore:
    """TrackingStore backed by .lume/workstreams/<slug>/ JSON files."""

    def __init__(self, lume_dir: Path) -> None:
        self._root = lume_dir / WORKSTREAMS_SUBDIR

    @classmethod
    def from_workstreams_root(cls, root: Path) -> "FilesystemStore":
        """Build a store whose workstreams root is `root` directly (the dir that
        holds <slug>/ subdirs). Used where the caller has that dir, not the .lume/."""
        store = cls.__new__(cls)
        store._root = root
        return store

    def _dir(self, slug: str) -> Path:
        return self._root / slug

    def _path(self, slug: str, artifact: str) -> Path:
        ws = self._dir(slug)
        if artifact == "state":
            return ws / state_mod.STATE_FILE
        if artifact.startswith("iteration:"):
            return ws / "iterations" / f"{artifact.split(':', 1)[1]}.json"
        if artifact in _SIMPLE_ARTIFACTS:
            return ws / f"{artifact}.json"
        raise ValueError(f"unknown artifact id '{artifact}'.")

    def list_workstreams(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(
            p.name for p in self._root.iterdir()
            if (p / state_mod.STATE_FILE).is_file()
        )

    def has_workstream(self, slug: str) -> bool:
        return (self._dir(slug) / state_mod.STATE_FILE).is_file()

    def create_workstream(self, slug: str) -> None:
        self._dir(slug).mkdir(parents=True, exist_ok=True)

    def read(self, slug: str, artifact: str) -> dict | None:
        path = self._path(slug, artifact)
        if not path.is_file():
            return None
        if artifact == "state":
            return state_mod.load(path)
        return json.loads(path.read_text())

    def write(self, slug: str, artifact: str, doc: dict) -> None:
        path = self._path(slug, artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact == "state":
            state_mod.save(path, doc)
        else:
            path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


class SQLiteStore:
    """TrackingStore backed by a single SQLite db - a non-filesystem proof that
    the contract is backing-agnostic. Artifacts are rows keyed by (slug, artifact);
    docs are stored as JSON text. The 'state' artifact is validated via
    state.validate_doc on read and write (no path I/O involved)."""

    def __init__(self, db_path: Path | str) -> None:
        # check_same_thread=False keeps it usable from tests; the CLI is single-threaded.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS artifacts ("
            " slug TEXT NOT NULL, artifact TEXT NOT NULL, doc TEXT NOT NULL,"
            " PRIMARY KEY (slug, artifact))"
        )
        self._conn.commit()

    def list_workstreams(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT slug FROM artifacts WHERE artifact = 'state' ORDER BY slug"
        ).fetchall()
        return [r[0] for r in rows]

    def has_workstream(self, slug: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM artifacts WHERE slug = ? AND artifact = 'state'", (slug,)
        ).fetchone()
        return row is not None

    def create_workstream(self, slug: str) -> None:
        # Rows appear on write; nothing to pre-create for a row store.
        pass

    def read(self, slug: str, artifact: str) -> dict | None:
        row = self._conn.execute(
            "SELECT doc FROM artifacts WHERE slug = ? AND artifact = ?", (slug, artifact)
        ).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        if artifact == "state":
            state_mod.validate_doc(doc)
        return doc

    def write(self, slug: str, artifact: str, doc: dict) -> None:
        if artifact == "state":
            state_mod.validate_doc(doc)
        self._conn.execute(
            "INSERT INTO artifacts (slug, artifact, doc) VALUES (?, ?, ?) "
            "ON CONFLICT(slug, artifact) DO UPDATE SET doc = excluded.doc",
            (slug, artifact, json.dumps(doc, indent=2, sort_keys=True)),
        )
        self._conn.commit()


class InMemoryStore:
    """TrackingStore over an in-process dict - a fast, dependency-free test double
    (no temp dirs, no db files). Stores deep copies so a caller mutating a returned
    doc can never reach back into stored state. 'state' is validated like any backing."""

    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], dict] = {}

    def list_workstreams(self) -> list[str]:
        return sorted({slug for (slug, artifact) in self._docs if artifact == "state"})

    def has_workstream(self, slug: str) -> bool:
        return (slug, "state") in self._docs

    def create_workstream(self, slug: str) -> None:
        pass

    def read(self, slug: str, artifact: str) -> dict | None:
        doc = self._docs.get((slug, artifact))
        if doc is None:
            return None
        if artifact == "state":
            state_mod.validate_doc(doc)
        return copy.deepcopy(doc)

    def write(self, slug: str, artifact: str, doc: dict) -> None:
        if artifact == "state":
            state_mod.validate_doc(doc)
        self._docs[(slug, artifact)] = copy.deepcopy(doc)
