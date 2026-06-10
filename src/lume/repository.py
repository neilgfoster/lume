"""The persistence/tracking seam: locate `.lume/` and resolve its workstream.

This is the documented boundary scope.md earmarks for the tracking contract -
today it is local files; a future GitHub Issues / Jira backing would replace
this class without touching the models above it. Kept concrete (not an abstract
base) until a second implementation actually pulls on it.

The start directory is injected so tests run against a temp tree, not the real
repo, and the engine can be invoked from any subdirectory of a project.
"""
from __future__ import annotations

import re
from pathlib import Path

from .clock import Clock
from .errors import GateError, LumeError, NoLumeDirError, NoWorkstreamError
from .store import FilesystemStore, TrackingStore
from .workstream import ACTIVE, Workstream

WORKSTREAMS_SUBDIR = "workstreams"
# A slug names a workstream; keep it path-safe.
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

_OBJECTIVE_PLACEHOLDER = "(objective: describe the done-when for this workstream)"


class Repository:
    def __init__(self, start: Path, clock: Clock, store: TrackingStore | None = None) -> None:
        self._start = start
        self._clock = clock
        # The Tracking contract. When not injected, default to a FilesystemStore
        # built lazily from the resolved .lume/ dir (see _store).
        self._injected_store = store

    def _store(self, lume_dir: Path) -> TrackingStore:
        """The TrackingStore to persist through: the injected one, else a FilesystemStore."""
        return self._injected_store or FilesystemStore(lume_dir)

    def find_lume_dir(self) -> Path | None:
        for directory in (self._start, *self._start.parents):
            candidate = directory / ".lume"
            if candidate.is_dir():
                return candidate
        return None

    def _require_lume_dir(self) -> Path:
        lume_dir = self.find_lume_dir()
        if lume_dir is None:
            raise NoLumeDirError("no .lume/ found from here.")
        return lume_dir

    def ensure_lume_dir(self) -> Path:
        """The operator's .lume/ dir, creating it at the start path if absent.

        Bootstrap path for `lume seed`: a fresh repo has no .lume/, so seed is
        the one verb that may create it (every other verb requires it to exist).
        """
        lume_dir = self.find_lume_dir()
        if lume_dir is None:
            lume_dir = self._start / ".lume"
            try:
                (lume_dir / WORKSTREAMS_SUBDIR).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise LumeError(f"cannot create .lume/ at {lume_dir}: {exc}") from exc
        return lume_dir

    def _load_workstream(self, lume_dir: Path, id: str) -> Workstream:
        """Load a workstream by its store id and return a store-backed Workstream."""
        store = self._store(lume_dir)
        doc = store.read(id, "state")
        if doc is None:
            raise LumeError(f"no state.json for id '{id}'; run: lume migrate")
        slug = doc["workstream"].get("slug", id)
        return Workstream(store, id, slug, self._clock, doc)

    def _slug_to_id(self, lume_dir: Path, slug: str) -> str | None:
        """Scan all workstreams to find the one whose slug label matches.

        Returns the store id, or None if not found.
        """
        store = self._store(lume_dir)
        for id in store.list_workstreams():
            doc = store.read(id, "state")
            if doc and doc["workstream"].get("slug") == slug:
                return id
        return None

    def workstreams(self, lume_dir: Path) -> list[Workstream]:
        """Every workstream as a Workstream, sorted by id."""
        return [self._load_workstream(lume_dir, id)
                for id in self._store(lume_dir).list_workstreams()]

    def active_workstreams(self, lume_dir: Path) -> list[Workstream]:
        return [ws for ws in self.workstreams(lume_dir) if not ws.is_closed]

    def workstream(self, slug_or_id: str | None = None) -> Workstream:
        """Resolve the workstream a command acts on.

        With `slug_or_id`, target it explicitly (the `-w` selector). Accepts
        a store id (e.g. "0007") or a slug label (e.g. "seed-and-numbering");
        id is tried first. A closed or unresolvable value is a named error.
        Without `slug_or_id`, default to the sole active workstream; zero or
        several active is a named error that never silently picks one.
        """
        lume_dir = self._require_lume_dir()
        if slug_or_id is not None:
            store = self._store(lume_dir)
            # Try as id first, then fall back to slug scan.
            if store.has_workstream(slug_or_id):
                id = slug_or_id
            else:
                id = self._slug_to_id(lume_dir, slug_or_id)
                if id is None:
                    raise NoWorkstreamError(
                        f"no workstream '{slug_or_id}' under {lume_dir}."
                    )
            ws = self._load_workstream(lume_dir, id)
            if ws.is_closed:
                raise GateError(
                    f"workstream '{slug_or_id}' is closed; reopen it or target another."
                )
            return ws
        active = self.active_workstreams(lume_dir)
        if not active:
            raise NoWorkstreamError(
                'no active workstream. Create one: lume new <slug> "<title>".'
            )
        if len(active) > 1:
            names = ", ".join(ws.name for ws in active)
            raise GateError(
                f"multiple active workstreams ({names}); pass -w <slug> to pick one."
            )
        return active[0]

    def reopen_workstream(self, slug: str) -> Workstream:
        """Reopen a closed workstream: flip status back to active in state + objective.

        Bypasses the closed-workstream gate in `workstream()`. Unknown slug or an
        already-active workstream is a named error.
        """
        lume_dir = self._require_lume_dir()
        id = self._slug_to_id(lume_dir, slug)
        if id is None:
            raise NoWorkstreamError(f"no workstream '{slug}' under {lume_dir}.")
        ws = self._load_workstream(lume_dir, id)
        if not ws.is_closed:
            raise GateError(f"workstream '{slug}' is already active.")
        ws.set_status(ACTIVE)
        return ws

    def load_state(self, id: str) -> dict:
        """Read + validate a workstream's state through the Tracking contract (by id)."""
        doc = self._store(self._require_lume_dir()).read(id, "state")
        if doc is None:
            raise LumeError(f"no state for id '{id}'.")
        return doc

    def save_state(self, id: str, doc: dict) -> None:
        """Validate + persist a workstream's state through the Tracking contract (by id)."""
        self._store(self._require_lume_dir()).write(id, "state", doc)

    def create_workstream(self, slug: str, title: str, seed: bool = False) -> Workstream:
        """Create a new active workstream with objective.json and state.json (JSON-only)."""
        lume_dir = self._require_lume_dir()
        if not _SLUG_RE.match(slug):
            raise GateError(
                f"invalid slug '{slug}': use letters/digits, '-' or '_', "
                "starting with a letter or digit."
            )
        store = self._store(lume_dir)
        if self._slug_to_id(lume_dir, slug) is not None:
            raise GateError(f"workstream '{slug}' already exists.")
        id = store.create_workstream(slug, seed=seed)
        ws_section: dict = {
            "id": id,
            "slug": slug,
            "title": title,
            "status": ACTIVE,
            "objective_artifact": "objective.json",
        }
        if seed:
            ws_section["seed"] = True
        initial_state: dict = {
            "workstream": ws_section,
            "iterations": [],
            "plan": [],
        }
        store.write(id, "state", initial_state)
        ws = Workstream(store, id, slug, self._clock, initial_state)
        obj_doc = {
            "slug": slug,
            "title": title,
            "status": ACTIVE,
            "text": _OBJECTIVE_PLACEHOLDER,
        }
        ws._save_objective(obj_doc)
        return ws
