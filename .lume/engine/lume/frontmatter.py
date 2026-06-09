"""Minimal YAML-style frontmatter: a leading `--- ... ---` block of `key: value`.

Deliberately not a full YAML parser - the engine only ever writes flat scalar
frontmatter, so this stays dependency-free and round-trips its own output.
"""
from __future__ import annotations

FENCE = "---"


def parse(text: str) -> tuple[dict[str, str], str]:
    """Split `text` into (frontmatter dict, body). No fence -> ({}, text)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return {}, text
    meta: dict[str, str] = {}
    body_start = len(lines)
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == FENCE:
            body_start = i + 1
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    body = "\n".join(lines[body_start:])
    return meta, body


def render(meta: dict[str, str], body: str) -> str:
    """Inverse of parse for flat scalar meta. Body is emitted verbatim."""
    out = [FENCE]
    out.extend(f"{key}: {value}" for key, value in meta.items())
    out.append(FENCE)
    text = "\n".join(out)
    if body:
        text += "\n" + body
    return text
