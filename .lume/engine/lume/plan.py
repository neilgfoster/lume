"""Parse the living plan.md into ordered items.

Pure parsing (no I/O): the Workstream reads the file and supplies the text.
A plan item line follows the schema documented at the top of plan.md:

    - P<n> | <type> | iter:<NNN|-> | <committed|optional> | <sketch>

Lines that do not match are ignored, so prose, headings, and the schema example
(`- P<n> | ...`, whose `<n>` is not digits) are skipped.
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
    iter: str | None  # "004", or None when the schema's "-" (not yet opened)
    tag: str          # "committed" | "optional"
    sketch: str

    @property
    def iter_id(self) -> int | None:
        return int(self.iter) if self.iter and self.iter.isdigit() else None


def parse_plan(text: str) -> list[PlanItem]:
    items: list[PlanItem] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line.strip())
        if not m:
            continue
        pid, ptype, piter, tag, sketch = (g.strip() for g in m.groups())
        items.append(
            PlanItem(
                id=pid,
                type=ptype,
                iter=None if piter == "-" else piter,
                tag=tag,
                sketch=sketch,
            )
        )
    return items
