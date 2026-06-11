"""CLI input/output: error + success emitters and the human/JSON renderers.

Output is human text by default; under --json, success emits one structured
result object and errors emit {"error": {"code", "message"}}. Exit codes are the
caller's responsibility and are identical with or without --json.
"""
from __future__ import annotations

import json
import sys

from ..dod_checks import verifiability_summary
from ..errors import GateError, NoLumeDirError, NoWorkstreamError, SchemaError
from ..workstream import Workstream


def _dod_verifiability(ws: Workstream) -> dict | None:
    """Static DoD-verifiability summary for the current iteration, or None.

    Counts only (no predicate executed) - safe in a read view; lets a caller
    see whether the current DoD is fully machine-checkable before accept.
    """
    content = ws.current_iteration_content()
    return verifiability_summary(content) if content else None

# Exception type -> stable machine-readable error code (decision F3).
_ERR_CODES: tuple[tuple[type, str], ...] = (
    (NoWorkstreamError, "not_found"),
    (NoLumeDirError, "no_lume_dir"),
    (SchemaError, "schema"),
    (GateError, "gate"),
)


def _code_for(exc: Exception) -> str:
    for typ, code in _ERR_CODES:
        if isinstance(exc, typ):
            return code
    return "error"


def _json_out(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _fail(json_mode: bool, code: str, message: str) -> None:
    """Emit an error: a JSON {error:{code,message}} under --json, else 'lume: <message>'.

    Exit codes (the primary signal) are chosen by the caller and unchanged."""
    if json_mode:
        print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
    else:
        print(f"lume: {message}", file=sys.stderr)


def _ok(json_mode: bool, data: dict, *human_lines: str) -> None:
    """Emit a success result: the JSON `data` object under --json, else the human lines.

    Mirrors _fail for errors so every verb's output goes through one shape."""
    if json_mode:
        _json_out(data)
    else:
        for line in human_lines:
            print(line)


def _render_detail(ws: Workstream, children: list[Workstream] | None = None) -> None:
    """Single-workstream view: objective, current iteration, Done/Now/Next."""
    current = ws.current_iteration()
    if current is None:
        iteration_line = "iteration: (none yet)"
    else:
        warn = "" if current.phase_valid else "  [!] unknown phase"
        iteration_line = (
            f"iteration {current.id:03d} ({current.type}): phase {current.phase}{warn}"
        )
    id_suffix = f"  [{ws.id}]" if ws.id != ws.name else ""
    print(f"# {ws.name}{id_suffix}")
    print(f"objective: {ws.objective_line()}")
    print(iteration_line)
    v = _dod_verifiability(ws)
    if v is not None and v["total"]:
        cmd_note = ", has command checks" if v["has_command_checks"] else ""
        print(
            f"DoD: {v['verifiable']}/{v['total']} verifiable, "
            f"{v['prose_only']} prose-only{cmd_note}"
        )
    print()
    print(ws.snapshot_done_now_next())
    if children:
        print()
        print("## Children")
        for c in children:
            it = c.current_iteration()
            where = f"{it.id:03d} {it.type} {it.phase}" if it is not None else "(no iterations)"
            print(f"- {c.name} [{c.id}]  {'closed' if c.is_closed else where}")


def _render_queue(workstreams: list[Workstream]) -> None:
    """Cross-workstream review queue: what's awaiting you, then in progress, then closed."""
    awaiting, in_progress, closed = [], [], []
    for ws in workstreams:
        if ws.is_closed:
            closed.append(ws)
            continue
        it = ws.current_iteration()
        if it is not None and it.phase == "handback":
            awaiting.append((ws, it))
        else:
            in_progress.append((ws, it))

    by_id = {ws.id: ws for ws in workstreams}

    def _ws_label(ws: Workstream) -> str:
        return f"{ws.name} [{ws.id}]" if ws.id != ws.name else ws.name

    def _row(ws: Workstream, where: str = "") -> str:
        # A child is indented and annotated with its parent within its bucket
        # (the queue groups by review status, not by hierarchy).
        body = f"{_ws_label(ws)}  {where}".rstrip()
        if ws.parent and ws.parent in by_id:
            return f"  - {body}  (child of {by_id[ws.parent].name})"
        return f"- {body}"

    print("# lume - review queue")
    print()
    print("## Awaiting you")
    if awaiting:
        for ws, it in awaiting:
            print(_row(ws, f"{it.id:03d} {it.type} handback"))
    else:
        print("- (nothing awaiting review)")
    print()
    print("## In progress")
    if in_progress:
        for ws, it in in_progress:
            where = (
                f"{it.id:03d} {it.type} {it.phase}" if it is not None else "(no iterations)"
            )
            print(_row(ws, where))
    else:
        print("- (none)")
    if closed:
        print()
        print("## Closed")
        for ws in closed:
            print(_row(ws))


def _iteration_summary(it) -> dict | None:
    if it is None:
        return None
    return {"id": it.id, "type": it.type, "phase": it.phase}


def _child_summary(ws: Workstream) -> dict:
    it = ws.current_iteration()
    return {"id": ws.id, "name": ws.name, "status": ws.status,
            "phase": it.phase if it is not None else None}


def _detail_data(ws: Workstream, children: list[Workstream] | None = None) -> dict:
    """Single-workstream status as a structured object (the --json form of _render_detail)."""
    return {
        "id": ws.id,
        "name": ws.name,
        "status": ws.status,
        "parent": ws.parent,
        "objective": ws.objective_line(),
        "current_iteration": _iteration_summary(ws.current_iteration()),
        "dod_verifiability": _dod_verifiability(ws),
        "children": [_child_summary(c) for c in (children or [])],
    }


def _queue_data(workstreams: list[Workstream]) -> dict:
    """Cross-workstream review queue as a structured object (the --json form of _render_queue)."""
    awaiting, in_progress, closed = [], [], []
    for ws in workstreams:
        if ws.is_closed:
            closed.append({"id": ws.id, "workstream": ws.name, "parent": ws.parent})
            continue
        it = ws.current_iteration()
        entry = {"id": ws.id, "workstream": ws.name, "parent": ws.parent,
                 "iteration": _iteration_summary(it)}
        if it is not None and it.phase == "handback":
            awaiting.append(entry)
        else:
            in_progress.append(entry)
    return {"awaiting": awaiting, "in_progress": in_progress, "closed": closed}
