"""CLI dispatch. Pure wiring: build the Repository from injected start/clock,
route the command, map errors to messages + exit codes. No domain logic here.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .clock import Clock, SystemClock
from .errors import GateError, LumeError
from .iteration import TRANSITIONS
from .repository import Repository
from .workstream import Workstream

_VERBS = " ".join(["status", "open", *TRANSITIONS])
USAGE = f'lume: usage: lume <{_VERBS}>   (open/reject take an argument)'


def _render_status(ws: Workstream) -> None:
    current = ws.current_iteration()
    if current is None:
        iteration_line = "iteration: (none yet)"
    else:
        warn = "" if current.phase_valid else "  [!] unknown phase"
        iteration_line = f"iteration {current.id:03d}: phase {current.phase}{warn}"
    print(f"# {ws.name}")
    print(f"objective: {ws.objective_line()}")
    print(iteration_line)
    print()
    print(ws.snapshot_done_now_next())


def main(argv: list[str], start: Path | None = None, clock: Clock | None = None) -> int:
    start = start or Path.cwd()
    clock = clock or SystemClock()

    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd not in ("status", "open", *TRANSITIONS):
        print(f"lume: unknown command '{cmd}'.\n{USAGE}", file=sys.stderr)
        return 2

    # Parse per-command arguments before touching the filesystem.
    arg = argv[2].strip() if len(argv) > 2 else ""
    if cmd == "open" and not arg:
        print('lume: usage: lume open "<title>"', file=sys.stderr)
        return 2
    if cmd == "reject" and not arg:
        print('lume: usage: lume reject "<reason>"  (a reason is required)', file=sys.stderr)
        return 2

    repo = Repository(start, clock)
    try:
        ws = repo.workstream()
    except LumeError as exc:
        print(f"lume: {exc}", file=sys.stderr)
        return 1

    if cmd == "status":
        _render_status(ws)
        return 0

    if cmd == "open":
        try:
            iteration = ws.open_iteration(arg)
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
