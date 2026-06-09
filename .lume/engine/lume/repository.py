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

from . import state
from .clock import Clock
from .errors import GateError, LumeError, NoLumeDirError, NoWorkstreamError
from .workstream import ACTIVE, Workstream

WORKSTREAMS_SUBDIR = "workstreams"
# A slug names a directory under workstreams/, so keep it path-safe.
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

_OBJECTIVE_PLACEHOLDER = "(objective: describe the done-when for this workstream)"


class Repository:
    def __init__(self, start: Path, clock: Clock) -> None:
        self._start = start
        self._clock = clock

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

    def _workstream_dirs(self, lume_dir: Path) -> list[Path]:
        root = lume_dir / WORKSTREAMS_SUBDIR
        if not root.is_dir():
            return []
        return sorted(p for p in root.iterdir() if (p / state.STATE_FILE).is_file())

    def _load_workstream(self, ws_dir: Path) -> Workstream:
        """Load state.json for ws_dir and return a state-backed Workstream."""
        state_path = ws_dir / state.STATE_FILE
        if not state_path.is_file():
            raise LumeError(
                f"no state.json for '{ws_dir.name}'; run: lume migrate"
            )
        doc = state.load(state_path)
        return Workstream(ws_dir, self._clock, doc)

    def workstreams(self, lume_dir: Path) -> list[Workstream]:
        """Every workstream as a Workstream, sorted by slug."""
        return [self._load_workstream(p) for p in self._workstream_dirs(lume_dir)]

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
            ws_dir = lume_dir / WORKSTREAMS_SUBDIR / slug
            if not (ws_dir / state.STATE_FILE).is_file():
                raise NoWorkstreamError(f"no workstream '{slug}' under {lume_dir}.")
            ws = self._load_workstream(ws_dir)
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

    def _state_path(self, slug: str) -> Path:
        return self._require_lume_dir() / WORKSTREAMS_SUBDIR / slug / state.STATE_FILE

    def load_state(self, slug: str) -> dict:
        """Read + validate `<slug>/state.json` (the JSON state seam, decision (f))."""
        return state.load(self._state_path(slug))

    def save_state(self, slug: str, doc: dict) -> None:
        """Validate then write `<slug>/state.json`, creating the dir if needed."""
        path = self._state_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        state.save(path, doc)

    def create_workstream(self, slug: str, title: str) -> Workstream:
        """Create a new active workstream with objective.json, objective.md view, and state.json."""
        lume_dir = self._require_lume_dir()
        if not _SLUG_RE.match(slug):
            raise GateError(
                f"invalid slug '{slug}': use letters/digits, '-' or '_', "
                "starting with a letter or digit."
            )
        ws_dir = lume_dir / WORKSTREAMS_SUBDIR / slug
        if ws_dir.exists():
            raise GateError(f"workstream '{slug}' already exists.")
        ws_dir.mkdir(parents=True)
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
        state.save(ws_dir / state.STATE_FILE, initial_state)
        ws = Workstream(ws_dir, self._clock, initial_state)
        obj_doc = {
            "slug": slug,
            "title": title,
            "status": ACTIVE,
            "text": _OBJECTIVE_PLACEHOLDER,
        }
        ws._save_objective(obj_doc)
        ws._render_objective(obj_doc)
        return ws
