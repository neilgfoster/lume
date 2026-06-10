"""The Iteration model: frontmatter-backed unit of the loop, with phase rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import frontmatter

# A verdict stamp line, exactly as a transition writes it:
#   2026-06-09 | ACCEPTED
#   2026-06-09 | REJECTED | some reason
# Anchored to a leading ISO date so prose mentioning ACCEPTED/REJECTED (a DoD
# line, a self-review note) never matches. This is the one canonical parser;
# migrate re-uses it.
_VERDICT_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*\|\s*(ACCEPTED|REJECTED)(?:\s*\|\s*(.*))?$"
)


def parse_verdicts(body: str) -> list[dict]:
    """Extract verdict stamps from an iteration body, oldest first."""
    verdicts = []
    for line in body.splitlines():
        m = _VERDICT_RE.match(line.strip())
        if not m:
            continue
        reason = m.group(3).strip() if m.group(3) and m.group(3).strip() else None
        verdicts.append({"date": m.group(1), "verdict": m.group(2).lower(), "reason": reason})
    return verdicts

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
SKELETONS: dict[str, str] = {
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

_ITEM_LINE_RE = re.compile(r"^-\s+\[([ x])\]\s+(.*)")


def parse_dod_items(skeleton: str) -> list[dict]:
    """Parse a skeleton string of `- [ ] text` lines into content-doc item dicts."""
    items = []
    for line in skeleton.strip().splitlines():
        m = _ITEM_LINE_RE.match(line)
        if m:
            items.append({"text": m.group(2).strip(), "checked": m.group(1) == "x"})
    return items


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
    # Verdicts as data. None -> derive from the body (preserving the markdown
    # path); a list -> the authoritative verdicts (used when built from state).
    verdicts: list | None = None

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

    def verdict_list(self) -> list[dict]:
        """The verdicts as data: the `verdicts` field if set, else parsed from the body."""
        return self.verdicts if self.verdicts is not None else parse_verdicts(self.body)

    def accepted_on(self) -> str | None:
        """Date from the last ACCEPTED verdict, if any."""
        for verdict in reversed(self.verdict_list()):
            if verdict["verdict"] == "accepted":
                return verdict["date"]
        return None

    def to_entity(self) -> dict:
        """This iteration as a P1 `iteration` state entity (prose stays in the artifact)."""
        return {
            "id": self.id,
            "type": self.type,
            "phase": self.phase,
            "opened": self.opened,
            "title": self.title,
            "verdicts": self.verdict_list(),
            "dod_artifact": f"iterations/{self.id:03d}.json",
        }

    @classmethod
    def from_entity(cls, entity: dict) -> "Iteration":
        """Rebuild an Iteration from a state entity. Body holds only the title heading
        (the prose lives in the artifact); verdicts come from the entity, not the body."""
        body = f"# Iteration {entity['id']:03d} - {entity['title']}\n"
        return cls(
            id=entity["id"],
            type=entity["type"],
            phase=entity["phase"],
            opened=entity["opened"],
            body=body,
            verdicts=list(entity["verdicts"]),
        )

    @property
    def phase_valid(self) -> bool:
        return self.phase in PHASES

    @classmethod
    def new(cls, id: int, title: str, opened: str, type: str = DEFAULT_TYPE) -> "Iteration":
        dod = SKELETONS.get(type, SKELETONS[DEFAULT_TYPE])
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
