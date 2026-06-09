"""CLI dispatch. Pure wiring: build the Repository from injected start/clock,
route the command, map errors to messages + exit codes. No domain logic here.

A workstream is selected with `-w <slug>` (alias `--workstream`), which may
appear anywhere in the args. Omitted, commands default to the sole active
workstream. `lume status` with no target is the cross-workstream review queue.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .clock import Clock, SystemClock
from .errors import GateError, LumeError
from .iteration import DEFAULT_TYPE, TRANSITIONS
from .repository import Repository
from .workstream import CLOSED, Workstream

_VERBS = " ".join(["status", "new", "open", "close", "snapshot", *TRANSITIONS])
USAGE = f'lume: usage: lume [-w <slug>] <{_VERBS}>   (new/open/reject take an argument)'


def _extract_flag(argv: list[str], aliases: tuple[str, ...], noun: str) -> tuple[str | None, list[str]]:
    """Pull `<alias> <value>` out of argv (anywhere); argv[0] is preserved.

    Returns (value or None, argv with the flag removed). Raises ValueError if an
    alias is given without a following value.
    """
    value: str | None = None
    rest = [argv[0]] if argv else []
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok in aliases:
            if i + 1 >= len(argv) or not argv[i + 1].strip():
                raise ValueError(f"{tok} needs {noun}.")
            value = argv[i + 1].strip()
            i += 2
            continue
        rest.append(tok)
        i += 1
    return value, rest


def _render_detail(ws: Workstream) -> None:
    """Single-workstream view: objective, current iteration, Done/Now/Next."""
    current = ws.current_iteration()
    if current is None:
        iteration_line = "iteration: (none yet)"
    else:
        warn = "" if current.phase_valid else "  [!] unknown phase"
        iteration_line = (
            f"iteration {current.id:03d} ({current.type}): phase {current.phase}{warn}"
        )
    print(f"# {ws.name}")
    print(f"objective: {ws.objective_line()}")
    print(iteration_line)
    print()
    print(ws.snapshot_done_now_next())


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

    print("# lume - review queue")
    print()
    print("## Awaiting you")
    if awaiting:
        for ws, it in awaiting:
            print(f"- {ws.name}  {it.id:03d} {it.type} handback")
    else:
        print("- (nothing awaiting review)")
    print()
    print("## In progress")
    if in_progress:
        for ws, it in in_progress:
            where = (
                f"{it.id:03d} {it.type} {it.phase}" if it is not None else "(no iterations)"
            )
            print(f"- {ws.name}  {where}")
    else:
        print("- (none)")
    if closed:
        print()
        print("## Closed")
        for ws in closed:
            print(f"- {ws.name}")


def main(argv: list[str], start: Path | None = None, clock: Clock | None = None) -> int:
    start = start or Path.cwd()
    clock = clock or SystemClock()

    try:
        target, rest = _extract_flag(argv, ("-w", "--workstream"), "a workstream slug")
        opt_type, rest = _extract_flag(rest, ("-t", "--type"), "a type")
    except ValueError as exc:
        print(f"lume: {exc}\n{USAGE}", file=sys.stderr)
        return 2

    cmd = rest[1] if len(rest) > 1 else "status"
    if cmd not in ("status", "new", "open", "close", "snapshot", *TRANSITIONS):
        print(f"lume: unknown command '{cmd}'.\n{USAGE}", file=sys.stderr)
        return 2

    # Parse per-command positional arguments before touching the filesystem.
    arg = rest[2].strip() if len(rest) > 2 else ""
    if cmd == "open" and not arg:
        print('lume: usage: lume open "<title>"', file=sys.stderr)
        return 2
    if cmd == "reject" and not arg:
        print('lume: usage: lume reject "<reason>"  (a reason is required)', file=sys.stderr)
        return 2
    if cmd == "new" and (not arg or not (len(rest) > 3 and rest[3].strip())):
        print('lume: usage: lume new <slug> "<title>"', file=sys.stderr)
        return 2

    repo = Repository(start, clock)

    # `new` names its workstream positionally; it needs no target resolution.
    if cmd == "new":
        try:
            ws = repo.create_workstream(arg, rest[3].strip())
        except LumeError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"created workstream '{ws.name}' (active): {ws.objective_path}")
        print('next: edit its objective.md, then: lume open "<first iteration>".')
        return 0

    # `status` with no target is the cross-workstream queue.
    if cmd == "status" and target is None:
        lume_dir = repo.find_lume_dir()
        if lume_dir is None:
            print("lume: no .lume/ found from here.", file=sys.stderr)
            return 1
        _render_queue(repo.workstreams(lume_dir))
        return 0

    # Everything else acts on one workstream: target via -w, else sole active.
    try:
        ws = repo.workstream(target)
    except LumeError as exc:
        print(f"lume: {exc}", file=sys.stderr)
        return 1

    if cmd == "status":
        _render_detail(ws)
        return 0

    if cmd == "close":
        ws.set_status(CLOSED)
        print(f"closed workstream '{ws.name}'.")
        return 0

    if cmd == "snapshot":
        path = ws.record_snapshot()
        note = "Next derived from plan.md" if ws.plan_items() is not None else "Next preserved"
        print(f"snapshot: regenerated Done/Now in {path} ({note})")
        return 0

    if cmd == "open":
        try:
            iteration = ws.open_iteration(arg, type=opt_type or DEFAULT_TYPE)
        except GateError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"opened iteration {iteration.id:03d}, phase {iteration.phase}: "
              f"{ws.iterations_dir / f'{iteration.id:03d}.md'}")
        print("next: draft its DoD, then have the operator approve before work starts.")
        return 0

    # cmd is a transition verb
    try:
        iteration = ws.transition(cmd, note=arg or None)
    except GateError as exc:
        print(f"lume: {exc}", file=sys.stderr)
        return 1
    print(f"{cmd}: iteration {iteration.id:03d} -> phase {iteration.phase}")
    return 0
