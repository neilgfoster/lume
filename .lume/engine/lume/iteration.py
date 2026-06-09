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

# The lifecycle-stage vocabulary an iteration's `type` is drawn from, and the
# default when `lume open` is given none.
# NOTE (plan P5): this will become a per-template property rather than a fixed
# module constant - see the lifecycle workstream's decisions.md (b).
TYPES: tuple[str, ...] = ("discovery", "planning", "execution", "closeout")
DEFAULT_TYPE = "execution"

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

# Per-type `## DoD` seed prompts (decision d): opening a typed iteration starts
# with the right shape of checkable items. These are prompts, not finished DoDs -
# the iteration still lands at `proposed` and the DoD is made crisp + approved.
# Data, keyed by type; `execution` keeps the original generic seed unchanged.
_SKELETONS: dict[str, str] = {
    "discovery": (
        "- [ ] Context built: the key questions for this stage are answered.\n"
        "- [ ] Artifact produced (e.g. discovery.md) capturing findings + open forks.\n"
        "- [ ] Scope held: no engine code; what is deferred to planning/execution is listed."
    ),
    "planning": (
        "- [ ] Decisions recorded: each open fork resolved with a one-line rationale.\n"
        "- [ ] Plan: the iterations to reach the objective, each a binary DoD sketch + committed/optional tag.\n"
        "- [ ] The first execution iteration is concrete enough to open next.\n"
        "- [ ] Scope held: no engine code."
    ),
    "execution": "- [ ] (propose checkable items)",
    "closeout": (
        "- [ ] Retro: did the work buy back more time than its ceremony cost? (per-step verdict)\n"
        "- [ ] Load-bearing assumptions checked against evidence.\n"
        "- [ ] Objective done-when assessed (met / not).\n"
        "- [ ] Decisions logged; workstream closed (lume close) and handed off."
    ),
}

_BODY_TEMPLATE = """\
# Iteration {id:03d} - {title}

## DoD
{dod}

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
    def title(self) -> str:
        """The iteration title, parsed from the first heading in the body.

        `# Iteration 004 - Some title` -> `Some title`.
        """
        for line in self.body.splitlines():
            if line.startswith("#"):
                heading = line.lstrip("# ").strip()
                marker = " - "
                if heading.lower().startswith("iteration") and marker in heading:
                    return heading.split(marker, 1)[1].strip()
                return heading
        return ""

    def accepted_on(self) -> str | None:
        """Date from the last ACCEPTED verdict line in the body, if any."""
        for line in reversed(self.body.splitlines()):
            if "ACCEPTED" in line and "|" in line:
                return line.split("|", 1)[0].strip()
        return None

    @property
    def phase_valid(self) -> bool:
        return self.phase in PHASES

    @classmethod
    def new(cls, id: int, title: str, opened: str, type: str = DEFAULT_TYPE) -> "Iteration":
        dod = _SKELETONS.get(type, _SKELETONS[DEFAULT_TYPE])
        return cls(
            id=id,
            type=type,
            phase="proposed",
            opened=opened,
            body=_BODY_TEMPLATE.format(id=id, title=title, dod=dod),
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
