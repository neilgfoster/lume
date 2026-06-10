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
# A slug names a directory under workstreams/, so keep it path-safe.
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

    def _load_workstream(self, lume_dir: Path, slug: str) -> Workstream:
        """Load a slug's state via the store and return a store-backed Workstream."""
        store = self._store(lume_dir)
        doc = store.read(slug, "state")
        if doc is None:
            raise LumeError(f"no state.json for '{slug}'; run: lume migrate")
        return Workstream(store, slug, self._clock, doc)

    def workstreams(self, lume_dir: Path) -> list[Workstream]:
        """Every workstream as a Workstream, sorted by slug."""
        return [self._load_workstream(lume_dir, slug)
                for slug in self._store(lume_dir).list_workstreams()]

    def active_workstreams(self, lume_dir: Path) -> list[Workstream]:
        return [ws for ws in self.workstreams(lume_dir) if not ws.is_closed]

    def workstream(self, slug: str | None = None) -> Workstream:
        """Resolve the workstream a command acts on.

        With `slug`, target it explicitly (the `-w` selector); a closed or
        unknown slug is a named error. Without `slug`, default to the sole
        active workstream; zero or several active is a named error that never
        silently picks one.
        """
        lume_dir = self._require_lume_dir()
        if slug is not None:
            if not self._store(lume_dir).has_workstream(slug):
                raise NoWorkstreamError(f"no workstream '{slug}' under {lume_dir}.")
            ws = self._load_workstream(lume_dir, slug)
            if ws.is_closed:
                raise GateError(
                    f"workstream '{slug}' is closed; reopen it or target another."
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
        if not self._store(lume_dir).has_workstream(slug):
            raise NoWorkstreamError(f"no workstream '{slug}' under {lume_dir}.")
        ws = self._load_workstream(lume_dir, slug)
        if not ws.is_closed:
            raise GateError(f"workstream '{slug}' is already active.")
        ws.set_status(ACTIVE)
        return ws

    def load_state(self, slug: str) -> dict:
        """Read + validate a slug's state through the Tracking contract."""
        doc = self._store(self._require_lume_dir()).read(slug, "state")
        if doc is None:
            raise LumeError(f"no state for '{slug}'.")
        return doc

    def save_state(self, slug: str, doc: dict) -> None:
        """Validate + persist a slug's state through the Tracking contract."""
        self._store(self._require_lume_dir()).write(slug, "state", doc)

    def create_workstream(self, slug: str, title: str) -> Workstream:
        """Create a new active workstream with objective.json and state.json (JSON-only)."""
        lume_dir = self._require_lume_dir()
        if not _SLUG_RE.match(slug):
            raise GateError(
                f"invalid slug '{slug}': use letters/digits, '-' or '_', "
                "starting with a letter or digit."
            )
        store = self._store(lume_dir)
        ws_dir = lume_dir / WORKSTREAMS_SUBDIR / slug
        if ws_dir.exists() or store.has_workstream(slug):
            raise GateError(f"workstream '{slug}' already exists.")
        store.create_workstream(slug)
        initial_state: dict = {
            "workstream": {
                "slug": slug,
                "title": title,
                "status": ACTIVE,
                "objective_artifact": "objective.json",
            },
            "iterations": [],
            "plan": [],
        }
        store.write(slug, "state", initial_state)
        ws = Workstream(store, slug, self._clock, initial_state)
        obj_doc = {
            "slug": slug,
            "title": title,
            "status": ACTIVE,
            "text": _OBJECTIVE_PLACEHOLDER,
        }
        ws._save_objective(obj_doc)
        return ws
