"""Minimal YAML-style frontmatter: a leading `--- ... ---` block of `key: value`.

Deliberately not a full YAML parser - the engine only ever writes flat scalar
frontmatter, so this stays dependency-free. parse/render are exact inverses:
the body is carried through verbatim (including its trailing newline), so a
phase-only edit rewrites a file byte-for-byte apart from the changed value.
"""
from __future__ import annotations

FENCE = "---"


def parse(text: str) -> tuple[dict[str, str], str]:
    """Split `text` into (frontmatter dict, body). No leading fence -> ({}, text)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != FENCE:
        return {}, text
    meta: dict[str, str] = {}
    body_start = len(lines)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == FENCE:
            body_start = i + 1
            break
        if ":" in lines[i]:
            key, _, value = lines[i].partition(":")
            meta[key.strip()] = value.strip()
    return meta, "".join(lines[body_start:])


def render(meta: dict[str, str], body: str) -> str:
    """Inverse of parse for flat scalar meta. Body is emitted verbatim."""
    out = [f"{FENCE}\n"]
    out.extend(f"{key}: {value}\n" for key, value in meta.items())
    out.append(f"{FENCE}\n")
    return "".join(out) + body
