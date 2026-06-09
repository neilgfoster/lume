"""Snapshot recorder: regenerate the Done/Now blocks from iteration state.

`build_snapshot` is a pure function (no I/O, date injected) so it is fully
unit-testable. It owns the title line, the `Updated:` stamp, and the `## Done`
and `## Now` sections; everything from `## Next` onward is hand-authored and
preserved verbatim. It is idempotent: re-running on its own output is a no-op.
"""
from __future__ import annotations

from .iteration import Iteration

_DEFAULT_TAIL = "## Next\n- (add next steps)\n"


def _tail_from(lines: list[str]) -> str:
    """Everything from the first `## Next` heading to EOF, else a default."""
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## next"):
            return "\n".join(lines[i:]).rstrip() + "\n"
    return _DEFAULT_TAIL


def build_snapshot(existing_text: str, iterations: list[Iteration], today: str) -> str:
    lines = existing_text.splitlines()
    title = lines[0] if lines and lines[0].startswith("#") else "# snapshot"
    tail = _tail_from(lines)
    latest = iterations[-1] if iterations else None

    if latest is None:
        updated = f"Updated: {today}"
        now = "- (no iterations yet)"
    else:
        updated = f"Updated: {today} (iteration {latest.id:03d} {latest.phase})"
        now = f"- {latest.id:03d} {latest.title} - phase {latest.phase}"

    accepted = sorted(
        (it for it in iterations if it.phase == "accepted"), key=lambda it: it.id
    )
    if accepted:
        done = "\n".join(
            f"- {it.id:03d} {it.title}"
            + (f" (accepted {it.accepted_on()})" if it.accepted_on() else "")
            for it in accepted
        )
    else:
        done = "- (nothing accepted yet)"

    return f"{title}\n\n{updated}\n\n## Done\n{done}\n\n## Now\n{now}\n\n{tail}"
