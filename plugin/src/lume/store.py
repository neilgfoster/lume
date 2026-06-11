"""The Tracking contract (scope.md): persistence of workstream/PM state.

A `TrackingStore` is the seam behind which a workstream's artifacts live. It is
a key/value of JSON documents addressed by (id, artifact), plus workstream
listing/creation. The engine's models and verbs talk to this contract, never to
files directly - so a second backing (SQLite, GitHub Issues, ...) swaps in
without touching anything above it. `Repository` is the policy/resolution layer
that *uses* a store; `FilesystemStore` is its v1 implementation.

Workstream ids are opaque strings, minted by the store on `create_workstream`.
FilesystemStore uses zero-padded sequential numbers ("0001", "0002", ...) with
folders named NNNN-slug on disk. SQLite and InMemory use their own sequences.

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
from .validate import validate_entity

WORKSTREAMS_SUBDIR = "workstreams"

# Artifact ids that map to a top-level <name>.json in the workstream dir.
_SIMPLE_ARTIFACTS = ("objective", "decisions", "retro", "discovery")


class TrackingStore(Protocol):
    def list_workstreams(self) -> list[str]: ...
    def has_workstream(self, id: str) -> bool: ...
    def create_workstream(self, slug: str, seed: bool = False) -> str: ...
    def read(self, id: str, artifact: str) -> dict | None: ...
    def write(self, id: str, artifact: str, doc: dict) -> None: ...
    # Reviews are repo-level (not workstream-keyed): one structured result per
    # dated review slug, validated against the discovery artifact shape.
    def read_review(self, slug: str) -> dict | None: ...
    def write_review(self, slug: str, doc: dict) -> None: ...
    def list_reviews(self) -> list[str]: ...


def _folder_id(name: str) -> str:
    """Extract the store id from a folder name.

    NNNN-slug -> "NNNN"; plain slug -> slug itself (legacy/test format).
    """
    parts = name.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[0]
    return name


def _folder_slug(name: str) -> str:
    """Extract the slug label from a folder name.

    NNNN-slug -> "slug"; plain slug -> slug itself.
    """
    parts = name.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1]
    return name


class FilesystemStore:
    """TrackingStore backed by .lume/workstreams/NNNN-<slug>/ JSON files.

    IDs are zero-padded sequential numbers ("0001", "0002", ...). The seed
    workstream (E3) uses "0000". Legacy plain-slug folders are also supported
    for migration compatibility; their id equals the folder name.
    """

    def __init__(self, lume_dir: Path) -> None:
        self._root = lume_dir / WORKSTREAMS_SUBDIR

    @classmethod
    def from_workstreams_root(cls, root: Path) -> "FilesystemStore":
        """Build a store whose workstreams root is `root` directly."""
        store = cls.__new__(cls)
        store._root = root
        return store

    def _next_id(self, seed: bool = False) -> str:
        if seed:
            return "0000"
        if not self._root.is_dir():
            return "0001"
        max_num = 0
        for p in self._root.iterdir():
            parts = p.name.split("-", 1)
            if len(parts) == 2 and parts[0].isdigit():
                max_num = max(max_num, int(parts[0]))
        return str(max_num + 1).zfill(4)

    def _dir_for_id(self, id: str) -> Path:
        """Resolve the workstream directory for `id`.

        Tries NNNN-slug prefix match first, then falls back to a literal
        folder name equal to `id` (supports plain-slug legacy/test dirs).
        """
        if self._root.is_dir():
            for p in self._root.iterdir():
                parts = p.name.split("-", 1)
                if len(parts) == 2 and parts[0] == id:
                    return p
            # Legacy fallback: folder name equals id
            candidate = self._root / id
            if candidate.is_dir():
                return candidate
        return self._root / id  # non-existent path; will fail on access

    def _path(self, id: str, artifact: str) -> Path:
        ws = self._dir_for_id(id)
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
        result = []
        for p in self._root.iterdir():
            if not (p / state_mod.STATE_FILE).is_file():
                continue
            result.append(_folder_id(p.name))
        return sorted(result)

    def has_workstream(self, id: str) -> bool:
        return (self._dir_for_id(id) / state_mod.STATE_FILE).is_file()

    def create_workstream(self, slug: str, seed: bool = False) -> str:
        id = self._next_id(seed=seed)
        folder = self._root / f"{id}-{slug}"
        folder.mkdir(parents=True, exist_ok=True)
        return id

    def read(self, id: str, artifact: str) -> dict | None:
        path = self._path(id, artifact)
        if not path.is_file():
            return None
        if artifact == "state":
            return state_mod.load(path)
        return json.loads(path.read_text())

    def write(self, id: str, artifact: str, doc: dict) -> None:
        path = self._path(id, artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact == "state":
            state_mod.save(path, doc)
        else:
            path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    def _review_path(self, slug: str) -> Path:
        # Reviews live under .lume/reviews/, beside workstreams/ and gaps/.
        return self._root.parent / "reviews" / slug / "result.json"

    def read_review(self, slug: str) -> dict | None:
        path = self._review_path(slug)
        if not path.is_file():
            return None
        doc = json.loads(path.read_text())
        validate_entity("discovery", doc)
        return doc

    def write_review(self, slug: str, doc: dict) -> None:
        validate_entity("discovery", doc)
        path = self._review_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    def list_reviews(self) -> list[str]:
        reviews_dir = self._root.parent / "reviews"
        if not reviews_dir.is_dir():
            return []
        return sorted(p.name for p in reviews_dir.iterdir()
                      if (p / "result.json").is_file())


class SQLiteStore:
    """TrackingStore backed by a single SQLite db - a non-filesystem proof that
    the contract is backing-agnostic. Workstream ids are auto-assigned row ids
    (returned as strings). Artifacts are rows keyed by (ws_id, artifact);
    docs are stored as JSON text. The 'state' artifact is validated via
    state.validate_doc on read and write (no path I/O involved)."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS workstreams ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " slug TEXT NOT NULL UNIQUE)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS artifacts ("
            " ws_id INTEGER NOT NULL, artifact TEXT NOT NULL, doc TEXT NOT NULL,"
            " PRIMARY KEY (ws_id, artifact))"
        )
        self._conn.commit()

    def list_workstreams(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM workstreams ORDER BY id"
        ).fetchall()
        return [str(r[0]) for r in rows]

    def has_workstream(self, id: str) -> bool:
        try:
            numeric_id = int(id)
        except ValueError:
            return False
        row = self._conn.execute(
            "SELECT 1 FROM workstreams WHERE id = ?", (numeric_id,)
        ).fetchone()
        return row is not None

    def create_workstream(self, slug: str, seed: bool = False) -> str:
        self._conn.execute("INSERT INTO workstreams (slug) VALUES (?)", (slug,))
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM workstreams WHERE slug = ?", (slug,)
        ).fetchone()
        return str(row[0])

    def read(self, id: str, artifact: str) -> dict | None:
        try:
            numeric_id = int(id)
        except ValueError:
            return None
        row = self._conn.execute(
            "SELECT doc FROM artifacts WHERE ws_id = ? AND artifact = ?",
            (numeric_id, artifact)
        ).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        if artifact == "state":
            state_mod.validate_doc(doc)
        return doc

    def write(self, id: str, artifact: str, doc: dict) -> None:
        if artifact == "state":
            state_mod.validate_doc(doc)
        self._conn.execute(
            "INSERT INTO artifacts (ws_id, artifact, doc) VALUES (?, ?, ?) "
            "ON CONFLICT(ws_id, artifact) DO UPDATE SET doc = excluded.doc",
            (int(id), artifact, json.dumps(doc, indent=2, sort_keys=True)),
        )
        self._conn.commit()

    def _ensure_reviews_table(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS reviews ("
            " slug TEXT PRIMARY KEY, doc TEXT NOT NULL)"
        )

    def read_review(self, slug: str) -> dict | None:
        self._ensure_reviews_table()
        row = self._conn.execute(
            "SELECT doc FROM reviews WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        validate_entity("discovery", doc)
        return doc

    def write_review(self, slug: str, doc: dict) -> None:
        validate_entity("discovery", doc)
        self._ensure_reviews_table()
        self._conn.execute(
            "INSERT INTO reviews (slug, doc) VALUES (?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET doc = excluded.doc",
            (slug, json.dumps(doc, indent=2, sort_keys=True)),
        )
        self._conn.commit()

    def list_reviews(self) -> list[str]:
        self._ensure_reviews_table()
        rows = self._conn.execute("SELECT slug FROM reviews ORDER BY slug").fetchall()
        return [r[0] for r in rows]


class InMemoryStore:
    """TrackingStore over an in-process dict - a fast, dependency-free test double
    (no temp dirs, no db files). Stores deep copies so a caller mutating a returned
    doc can never reach back into stored state. 'state' is validated like any backing."""

    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], dict] = {}
        self._counter: int = 0

    def list_workstreams(self) -> list[str]:
        return sorted({id for (id, artifact) in self._docs if artifact == "state"})

    def has_workstream(self, id: str) -> bool:
        return (id, "state") in self._docs

    def create_workstream(self, slug: str, seed: bool = False) -> str:
        self._counter += 1
        return str(self._counter).zfill(4)

    def read(self, id: str, artifact: str) -> dict | None:
        doc = self._docs.get((id, artifact))
        if doc is None:
            return None
        if artifact == "state":
            state_mod.validate_doc(doc)
        return copy.deepcopy(doc)

    def write(self, id: str, artifact: str, doc: dict) -> None:
        if artifact == "state":
            state_mod.validate_doc(doc)
        self._docs[(id, artifact)] = copy.deepcopy(doc)

    def read_review(self, slug: str) -> dict | None:
        doc = self._docs.get(("@review", slug))
        return copy.deepcopy(doc) if doc is not None else None

    def write_review(self, slug: str, doc: dict) -> None:
        validate_entity("discovery", doc)
        self._docs[("@review", slug)] = copy.deepcopy(doc)

    def list_reviews(self) -> list[str]:
        return sorted(slug for (id, slug) in self._docs if id == "@review")
