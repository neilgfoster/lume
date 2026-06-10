"""Decisions log as data (P12).

`decisions.json` ({entries: [{date, context, decision, rationale}]}) is the
source of truth. The legacy hand-authored log it replaced used one line per
entry:

    - DATE | CONTEXT DECISION | RATIONALE

where CONTEXT is a leading parenthetical (e.g. "(002 planning)").
`parse_decisions_md` is the one-shot migration reader for that format.
"""
from __future__ import annotations

import re

_LINE_RE = re.compile(r"^-\s+(?P<date>\S+)\s+\|\s+(?P<mid>.*?)\s+\|\s+(?P<rationale>.*)$")
_CONTEXT_RE = re.compile(r"^(\([^)]*\))\s*(.*)$", re.DOTALL)


def parse_decisions_md(text: str) -> list[dict]:
    """Parse an append-only decisions.md into a list of decision entries.

    The inverse of render: each `- DATE | CONTEXT DECISION | RATIONALE` line
    becomes one entry; a leading parenthetical in the middle is the context.
    """
    entries: list[dict] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        mid = m.group("mid").strip()
        cm = _CONTEXT_RE.match(mid)
        if cm:
            context, decision = cm.group(1).strip(), cm.group(2).strip()
        else:
            context, decision = "", mid
        entries.append({
            "date": m.group("date").strip(),
            "context": context,
            "decision": decision,
            "rationale": m.group("rationale").strip(),
        })
    return entries
