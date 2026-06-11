#!/usr/bin/env python3
"""Render ADOPTERS.md's table from ADOPTERS.json (the source of truth).

ADOPTERS.json is what lume's scan reads; ADOPTERS.md is the human view. This
keeps the markdown table in sync by regenerating only the marker-delimited
region, leaving the curated prose untouched.

    python tools/render_adopters.py            # rewrite the table region
    python tools/render_adopters.py --check     # exit 1 if out of sync (CI/DoD)

Stdlib-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADOPTERS_JSON = REPO_ROOT / "ADOPTERS.json"
ADOPTERS_MD = REPO_ROOT / "ADOPTERS.md"
BEGIN = "<!-- BEGIN generated adopters table (source: ADOPTERS.json; run tools/render_adopters.py) -->"
END = "<!-- END generated adopters table -->"


def render_table(adopters: list[dict]) -> str:
    lines = ["| Project | Adopter | Link | Since |", "| --- | --- | --- | --- |"]
    for a in adopters:
        lines.append(f"| {a['project']} | {a['adopter']} | {a['url']} | {a['since']} |")
    return "\n".join(lines)


def render_md(md_text: str, adopters: list[dict]) -> str:
    """Return md_text with the BEGIN..END region replaced by the rendered table."""
    if BEGIN not in md_text or END not in md_text:
        raise SystemExit("ADOPTERS.md is missing the generated-table markers.")
    head, rest = md_text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{BEGIN}\n{render_table(adopters)}\n{END}{tail}"


def main(argv: list[str]) -> int:
    adopters = json.loads(ADOPTERS_JSON.read_text())["adopters"]
    current = ADOPTERS_MD.read_text()
    rendered = render_md(current, adopters)
    if "--check" in argv[1:]:
        if rendered != current:
            print("ADOPTERS.md is out of sync with ADOPTERS.json "
                  "(run: python tools/render_adopters.py)", file=sys.stderr)
            return 1
        print("ADOPTERS.md matches ADOPTERS.json.")
        return 0
    ADOPTERS_MD.write_text(rendered)
    print("rendered ADOPTERS.md from ADOPTERS.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
