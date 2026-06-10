"""Plan item model and parser.

`parse_plan` is kept for the migrate path (reads legacy plan.md files).
The engine no longer calls it during normal operation — state.json is the source.
JSON-only: there is no plan.md view, so no renderer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_ITEM_RE = re.compile(
    r"^-\s*(P\d+)\s*\|\s*([^|]+?)\s*\|\s*iter:\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.*)$"
)


@dataclass
class PlanItem:
    id: str           # "P1"
    type: str         # "execution"
    iter: int | None  # integer iteration id, or None when not yet opened
    tag: str          # "committed" | "optional"
    sketch: str

    @property
    def iter_id(self) -> int | None:
        return self.iter

    def to_entity(self) -> dict:
        """This plan item as a state plan_item entity."""
        return {
            "id": self.id,
            "iter": self.iter,
            "sketch": self.sketch,
            "tag": self.tag,
            "type": self.type,
        }

    @classmethod
    def from_entity(cls, entity: dict) -> "PlanItem":
        """Reconstruct a PlanItem from a state plan_item entity dict."""
        return cls(
            id=entity["id"],
            type=entity["type"],
            iter=entity.get("iter"),
            tag=entity["tag"],
            sketch=entity["sketch"],
        )


def parse_plan(text: str) -> list[PlanItem]:
    """Parse a plan.md into PlanItems. Used by migrate only."""
    items: list[PlanItem] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line.strip())
        if not m:
            continue
        pid, ptype, piter, tag, sketch = (g.strip() for g in m.groups())
        iter_val: int | None = None
        if piter != "-":
            try:
                iter_val = int(piter.lstrip("0") or "0")
            except ValueError:
                pass
        items.append(PlanItem(id=pid, type=ptype, iter=iter_val, tag=tag, sketch=sketch))
    return items
