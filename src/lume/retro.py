"""Retro as data (P12).

`retro.json` (schema: retro) is the source of truth. The schema captures the
recurring shape of the close-out retros (a per-stage verdict table, an objective
done-when table, an overall verdict, carry-forwards, and any other `## section`
verbatim). `parse_retro_md` is the one-shot, lossless migration reader for the
legacy hand-authored retro.md.
"""
from __future__ import annotations

import re

_OVERALL_FALLBACK = "(migrated from retro.md; see file history)"


def _parse_tables(text: str) -> list[list[dict]]:
    """Parse every markdown pipe-table into a list of header-keyed row dicts."""
    tables: list[list[dict]] = []
    rows: list[list[str]] = []

    def flush() -> None:
        if len(rows) >= 2:
            header = [c.strip().lower() for c in rows[0]]
            body = []
            for r in rows[2:]:  # skip the |---|---| separator row
                body.append({header[i]: (r[i].strip() if i < len(r) else "")
                             for i in range(len(header))})
            if body:
                tables.append(body)
        rows.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            rows.append([c for c in s.strip("|").split("|")])
        else:
            flush()
    flush()
    return tables


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into ordered (heading, body) pairs at `## ` boundaries."""
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            if heading is not None:
                sections.append((heading, "\n".join(body).strip()))
            heading = m.group(1)
            body = []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        sections.append((heading, "\n".join(body).strip()))
    return sections


# Headings whose content is captured into structured fields, not `sections`.
_STAGE_RE = re.compile(r"per-(stage|step)\s+verdict", re.IGNORECASE)
_DONE_RE = re.compile(r"(objective\s+)?done-when", re.IGNORECASE)
_OVERALL_RE = re.compile(r"overall\s+verdict", re.IGNORECASE)
_CARRY_RE = re.compile(r"(handoff|carry-forwards?)", re.IGNORECASE)


def parse_retro_md(text: str) -> dict:
    """Best-effort, lossless parse of a freeform retro.md into a retro doc.

    Recovers the structured tables (stage verdicts, done-when), the overall
    verdict and carry-forwards by their conventional headings; every other
    `## section` is preserved verbatim in `sections` so render round-trips the
    full document. Always returns a schema-valid doc.
    """
    stage_verdicts: list[dict] = []
    done_when: list[dict] = []

    for table in _parse_tables(text):
        cols = set(table[0].keys())
        if {"cost", "net"} <= cols:
            for row in table:
                entry = {
                    "stage": row.get("stage") or row.get("step") or "",
                    "cost": row.get("cost", ""),
                    "saved": row.get("saved") or row.get("saves") or "",
                    "net": row.get("net", ""),
                }
                if row.get("iterations"):
                    entry["iterations"] = row["iterations"]
                stage_verdicts.append(entry)
        elif {"verdict", "evidence"} <= cols:
            for row in table:
                done_when.append({
                    "clause": row.get("clause") or row.get("step") or "",
                    "verdict": row.get("verdict", ""),
                    "evidence": row.get("evidence", ""),
                })

    overall = _OVERALL_FALLBACK
    carry: list[str] = []
    sections: list[dict] = []

    for heading, body in _split_sections(text):
        if _OVERALL_RE.search(heading):
            overall = body or overall
        elif _CARRY_RE.search(heading):
            bullets = [s[2:].strip() for s in body.splitlines()
                       if s.strip().startswith(("- ", "* "))]
            carry = bullets or ([body] if body else [])
        elif _STAGE_RE.search(heading) or _DONE_RE.search(heading):
            continue  # captured into structured fields above
        else:
            sections.append({"heading": heading, "body": body})

    doc: dict = {"overall_verdict": overall, "carry_forwards": carry}
    if stage_verdicts:
        doc["stage_verdicts"] = stage_verdicts
    if done_when:
        doc["done_when"] = done_when
    if sections:
        doc["sections"] = sections
    return doc
