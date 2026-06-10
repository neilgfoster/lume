"""Snapshot recorder: regenerate the Done/Now blocks from iteration state.

`build_snapshot` is a pure function (no I/O, date injected) so it is fully
unit-testable. It owns the title line, the `Updated:` stamp, and the `## Done`
and `## Now` sections; everything from `## Next` onward is hand-authored and
preserved verbatim. It is idempotent: re-running on its own output is a no-op.
"""
from __future__ import annotations

from .iteration import Iteration
from .plan import PlanItem

_DEFAULT_TAIL = "## Next\n- (add next steps)\n"
_SKETCH_MAX = 90


def _tail_from(lines: list[str]) -> str:
    """Everything from the first `## Next` heading to EOF, else a default."""
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## next"):
            return "\n".join(lines[i:]).rstrip() + "\n"
    return _DEFAULT_TAIL


def _derived_next(plan_items: list[PlanItem], accepted_ids: set[int]) -> str:
    """Render the `## Next` block from the plan: position + the next item + the rest.

    Done = the item's linked iteration is accepted; next = first not-done item.
    """
    if not plan_items:
        return "## Next\n- (plan has no items)\n"
    total = len(plan_items)
    not_done = [
        it for it in plan_items if not (it.iter_id is not None and it.iter_id in accepted_ids)
    ]
    if not not_done:
        return f"## Next\n- plan.md: all {total} items done\n"
    nxt = not_done[0]
    step = plan_items.index(nxt) + 1
    sketch = nxt.sketch
    if len(sketch) > _SKETCH_MAX:
        sketch = sketch[:_SKETCH_MAX].rstrip() + "..."
    lines = [
        "## Next",
        f"- plan.md: step {step} of {total}",
        f"- > {nxt.id} ({nxt.type}): {sketch}",
    ]
    rest = not_done[1:]
    if rest:
        lines.append("- then: " + ", ".join(f"{it.id} ({it.type})" for it in rest))
    return "\n".join(lines) + "\n"


def build_snapshot(
    existing_text: str,
    iterations: list[Iteration],
    today: str,
    plan_items: list[PlanItem] | None = None,
) -> str:
    lines = existing_text.splitlines()
    title = lines[0] if lines and lines[0].startswith("#") else "# snapshot"
    if plan_items is None:
        tail = _tail_from(lines)  # no plan.md: preserve hand-authored Next
    else:
        accepted_ids = {it.id for it in iterations if it.phase == "accepted"}
        tail = _derived_next(plan_items, accepted_ids)
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
