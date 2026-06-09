"""The persistence/tracking seam: locate `.lume/` and resolve its workstream.

This is the documented boundary scope.md earmarks for the tracking contract -
today it is local files; a future GitHub Issues / Jira backing would replace
this class without touching the models above it. Kept concrete (not an abstract
base) until a second implementation actually pulls on it.

The start directory is injected so tests run against a temp tree, not the real
repo, and the engine can be invoked from any subdirectory of a project.
"""
from __future__ import annotations

from pathlib import Path

from .clock import Clock
from .errors import NoLumeDirError, NoWorkstreamError
from .workstream import Workstream

WORKSTREAMS_SUBDIR = "workstreams"


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

    def _workstream_dirs(self, lume_dir: Path) -> list[Path]:
        root = lume_dir / WORKSTREAMS_SUBDIR
        if not root.is_dir():
            return []
        return sorted(p for p in root.iterdir() if (p / "objective.md").is_file())

    def workstream(self) -> Workstream:
        """Resolve the single active workstream (v1 assumes one)."""
        lume_dir = self.find_lume_dir()
        if lume_dir is None:
            raise NoLumeDirError("no .lume/ found from here.")
        dirs = self._workstream_dirs(lume_dir)
        if not dirs:
            raise NoWorkstreamError(
                f"no workstream under {lume_dir / WORKSTREAMS_SUBDIR} "
                "(need a subdir with objective.md)."
            )
        # v1 is single-workstream; if several exist, the first is used.
        return Workstream(dirs[0], self._clock)
