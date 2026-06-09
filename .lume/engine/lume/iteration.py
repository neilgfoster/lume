"""The Iteration model: frontmatter-backed unit of the loop, with phase rules."""
from __future__ import annotations

from dataclasses import dataclass

from . import frontmatter

PHASES: tuple[str, ...] = (
    "proposed",
    "approved",
    "working",
    "handback",
    "accepted",
    "rejected",
)

# Phase that must hold on the latest iteration before a new one may open.
OPENABLE_AFTER = "accepted"

# The only legal phase moves, keyed by the verb that applies them. A verb maps
# to a fixed (from-phase -> to-phase) pair, so an arbitrary phase can never be set.
TRANSITIONS: dict[str, tuple[str, str]] = {
    "approve": ("proposed", "approved"),
    "start": ("approved", "working"),
    "handback": ("working", "handback"),
    "accept": ("handback", "accepted"),
    "reject": ("handback", "rejected"),
    "redo": ("rejected", "working"),
}

# Verbs that also record a dated note in the iteration's Verdict section.
VERDICT_LABELS: dict[str, str] = {"accept": "ACCEPTED", "reject": "REJECTED"}

_BODY_TEMPLATE = """\
# Iteration {id:03d} - {title}

## DoD
- [ ] (propose checkable items)

## Self-review
(filled at hand-back)

## Handback
(filled at hand-back)

## Verdict
(operator: accept / reject + reasons)
"""


@dataclass
class Iteration:
    id: int
    type: str
    phase: str
    opened: str
    body: str = ""

    @property
    def is_accepted(self) -> bool:
        return self.phase == OPENABLE_AFTER

    @property
    def phase_valid(self) -> bool:
        return self.phase in PHASES

    @classmethod
    def new(cls, id: int, title: str, opened: str, type: str = "build") -> "Iteration":
        return cls(
            id=id,
            type=type,
            phase="proposed",
            opened=opened,
            body=_BODY_TEMPLATE.format(id=id, title=title),
        )

    @classmethod
    def from_text(cls, text: str) -> "Iteration":
        meta, body = frontmatter.parse(text)
        return cls(
            id=int(meta["id"]),
            type=meta.get("type", "build"),
            phase=meta.get("phase", "?"),
            opened=meta.get("opened", ""),
            body=body,
        )

    def to_text(self) -> str:
        meta = {
            "id": f"{self.id:03d}",
            "type": self.type,
            "phase": self.phase,
            "opened": self.opened,
        }
        return frontmatter.render(meta, self.body)
