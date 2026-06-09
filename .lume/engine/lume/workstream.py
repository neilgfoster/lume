"""The Workstream model: a directory of objective + snapshot + iterations.

Owns the deterministic control logic for the loop (currently: opening the next
iteration through the no-double-open gate). The Clock is injected so the
`opened` date is deterministic and tests need no real wall-clock.
"""
from __future__ import annotations

from pathlib import Path

from .clock import Clock
from .errors import GateError
from .iteration import Iteration, OPENABLE_AFTER


class Workstream:
    def __init__(self, path: Path, clock: Clock) -> None:
        self._path = path
        self._clock = clock

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def iterations_dir(self) -> Path:
        return self._path / "iterations"

    def objective_line(self) -> str:
        """First non-empty line of objective.md, stripped of heading marks."""
        text = (self._path / "objective.md").read_text()
        for line in text.splitlines():
            stripped = line.lstrip("# ").strip()
            if stripped:
                return stripped
        return "(empty objective)"

    def snapshot_done_now_next(self) -> str:
        """Verbatim slice of snapshot.md from the first `## Done` to EOF."""
        snap = self._path / "snapshot.md"
        if not snap.is_file():
            return "(no snapshot)"
        lines = snap.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("## done"):
                return "\n".join(lines[i:]).rstrip()
        return snap.read_text().rstrip()

    def _iteration_files(self) -> list[Path]:
        if not self.iterations_dir.is_dir():
            return []
        return sorted(p for p in self.iterations_dir.glob("*.md") if p.stem.isdigit())

    def iteration_ids(self) -> list[int]:
        return [int(p.stem) for p in self._iteration_files()]

    def current_iteration(self) -> Iteration | None:
        files = self._iteration_files()
        if not files:
            return None
        return Iteration.from_text(files[-1].read_text())

    def open_iteration(self, title: str) -> Iteration:
        """Create the next iteration at phase 'proposed'.

        Gate: refuse unless the latest iteration is accepted (none = first open).
        """
        latest = self.current_iteration()
        if latest is not None and not latest.is_accepted:
            raise GateError(
                f"cannot open - iteration {latest.id:03d} is phase '{latest.phase}', "
                f"not '{OPENABLE_AFTER}'. Accept (or reject -> redo -> accept) it first."
            )
        ids = self.iteration_ids()
        next_id = (max(ids) + 1) if ids else 1
        iteration = Iteration.new(
            id=next_id, title=title, opened=self._clock.today().isoformat()
        )
        self.iterations_dir.mkdir(exist_ok=True)
        (self.iterations_dir / f"{next_id:03d}.md").write_text(iteration.to_text())
        return iteration
