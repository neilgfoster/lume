"""The Workstream model: a directory of objective + snapshot + iterations.

Owns the deterministic control logic for the loop (currently: opening the next
iteration through the no-double-open gate). The Clock is injected so the
`opened` date is deterministic and tests need no real wall-clock.
"""
from __future__ import annotations

from pathlib import Path

from . import frontmatter
from .clock import Clock
from .errors import GateError
from .iteration import (
    DEFAULT_TYPE,
    Iteration,
    OPENABLE_AFTER,
    TRANSITIONS,
    TYPES,
    VERDICT_LABELS,
)
from .plan import PlanItem, parse_plan
from .snapshot import build_snapshot

# Lifecycle state of a whole workstream, held in objective.md frontmatter.
ACTIVE = "active"
CLOSED = "closed"


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

    @property
    def objective_path(self) -> Path:
        return self._path / "objective.md"

    def _objective(self) -> tuple[dict[str, str], str]:
        """(frontmatter, body) of objective.md. Absent frontmatter -> ({}, text)."""
        return frontmatter.parse((self._path / "objective.md").read_text())

    @property
    def status(self) -> str:
        """`active` or `closed`. Absent/unmigrated frontmatter reads as active."""
        meta, _ = self._objective()
        return meta.get("status", ACTIVE)

    @property
    def is_closed(self) -> bool:
        return self.status == CLOSED

    def set_status(self, status: str) -> None:
        """Write `status` into objective.md frontmatter, preserving the body.

        If the file had no frontmatter (an unmigrated workstream), a block is
        added - this is the migration mechanic.
        """
        path = self._path / "objective.md"
        meta, body = frontmatter.parse(path.read_text())
        meta["status"] = status
        path.write_text(frontmatter.render(meta, body))

    def objective_line(self) -> str:
        """First non-empty body line of objective.md, stripped of heading marks.

        Frontmatter is skipped so the `status:` line is never mistaken for the
        objective text.
        """
        _, body = self._objective()
        for line in body.splitlines():
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

    def open_iteration(self, title: str, type: str = DEFAULT_TYPE) -> Iteration:
        """Create the next iteration at phase 'proposed', then refresh snapshot.md.

        Gate: refuse unless the latest iteration is accepted (none = first open).
        The type must be one of TYPES (validated here, in the control path, not
        in the CLI); nothing is written on a bad type.
        """
        if type not in TYPES:
            raise GateError(
                f"unknown iteration type '{type}'. Allowed: {', '.join(TYPES)}."
            )
        latest = self.current_iteration()
        if latest is not None and not latest.is_accepted:
            raise GateError(
                f"cannot open - iteration {latest.id:03d} is phase '{latest.phase}', "
                f"not '{OPENABLE_AFTER}'. Accept (or reject -> redo -> accept) it first."
            )
        ids = self.iteration_ids()
        next_id = (max(ids) + 1) if ids else 1
        iteration = Iteration.new(
            id=next_id, title=title, opened=self._clock.today().isoformat(), type=type
        )
        self.iterations_dir.mkdir(exist_ok=True)
        (self.iterations_dir / f"{next_id:03d}.md").write_text(iteration.to_text())
        self.record_snapshot()
        return iteration

    def plan_items(self) -> list[PlanItem] | None:
        """Parsed plan.md items, or None when the workstream has no plan.md.

        None (no plan) -> the snapshot preserves a hand-authored `## Next`;
        a present-but-empty plan -> [] -> a derived "(plan has no items)" Next.
        """
        plan = self._path / "plan.md"
        if not plan.is_file():
            return None
        return parse_plan(plan.read_text())

    def record_snapshot(self) -> Path:
        """Regenerate snapshot.md from iteration state. Writes only snapshot.md.

        With a plan.md, the `## Next` block is derived from it (next item +
        position); without one, the hand-authored `## Next` is preserved.
        """
        snap = self._path / "snapshot.md"
        existing = snap.read_text() if snap.is_file() else f"# {self.name} - snapshot\n"
        iterations = [Iteration.from_text(p.read_text()) for p in self._iteration_files()]
        snap.write_text(
            build_snapshot(
                existing,
                iterations,
                self._clock.today().isoformat(),
                plan_items=self.plan_items(),
            )
        )
        return snap

    def transition(self, verb: str, note: str | None = None) -> Iteration:
        """Apply a named phase transition to the current iteration.

        Validates the move against the transition table (refusing if the
        iteration is not in the verb's source phase) and, for accept/reject,
        appends a dated verdict line. Writes the current iteration file and
        then refreshes snapshot.md so Done/Now stay current with zero extra
        steps.
        """
        if verb not in TRANSITIONS:
            raise GateError(f"unknown transition '{verb}'.")
        iteration = self.current_iteration()
        if iteration is None:
            raise GateError("no iteration to transition.")
        source, target = TRANSITIONS[verb]
        if iteration.phase != source:
            raise GateError(
                f"cannot {verb} - iteration {iteration.id:03d} is phase "
                f"'{iteration.phase}', not '{source}'."
            )
        iteration.phase = target
        if verb in VERDICT_LABELS:
            stamp = f"{self._clock.today().isoformat()} | {VERDICT_LABELS[verb]}"
            # Only reject records a reason; accept never carries one.
            if verb == "reject" and note:
                stamp += f" | {note}"
            iteration.body = iteration.body.rstrip("\n") + "\n" + stamp + "\n"
        (self.iterations_dir / f"{iteration.id:03d}.md").write_text(iteration.to_text())
        self.record_snapshot()
        return iteration
