"""Discovery prose as data (P14).

`discovery.json` (schema: discovery) holds the authored discovery write-up as
{title, sections: [{heading, body}]}. It is the JSON-only successor to the
hand-authored discovery.md. `parse_discovery_md` is the one-shot migration
inverse: the leading `# ` line is the title and each `## ` section becomes a
{heading, body} pair with nested `###` content kept verbatim in the body.
"""
from __future__ import annotations

import re


def parse_discovery_md(text: str) -> dict:
    """Parse a discovery.md into a discovery doc {title?, sections:[...]}."""
    lines = text.splitlines()
    title: str | None = None
    sections: list[dict] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        if heading is not None:
            sections.append({"heading": heading, "body": "\n".join(body).strip()})

    for line in lines:
        h2 = re.match(r"^##\s+(.*?)\s*$", line)
        h1 = re.match(r"^#\s+(.*?)\s*$", line)
        if h2:
            flush()
            heading = h2.group(1)
            body = []
        elif h1 and title is None and heading is None:
            title = h1.group(1)
        elif heading is not None:
            body.append(line)
    flush()

    doc: dict = {"sections": sections}
    if title is not None:
        doc["title"] = title
    return doc
