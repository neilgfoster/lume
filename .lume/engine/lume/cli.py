"""CLI dispatch. Pure wiring: build the Repository from injected start/clock,
route the command, map errors to messages + exit codes. No domain logic here.

A workstream is selected with `-w <slug>` (alias `--workstream`), which may
appear anywhere in the args. Omitted, commands default to the sole active
workstream. `lume status` with no target is the cross-workstream review queue.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import migrate as migrate_mod
from .clock import Clock, SystemClock
from .errors import GateError, LumeError, SchemaError
from .iteration import DEFAULT_TYPE, TRANSITIONS
from .repository import Repository
from .store import SQLiteStore
from .validate import entity_kinds, load_schema
from .workstream import CLOSED, Workstream

# Entity kind -> state doc key (for `lume get`).
_ENTITY_KEY = {
    "workstream": "workstream",
    "iteration": "iterations",
    "plan_item": "plan",
}

_VERBS = " ".join([
    "status", "new", "open", "close", "reopen", "snapshot", "migrate",
    "entities", "schema", "get", "plan", "decide", "retro",
    *TRANSITIONS,
])
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


def _json_out(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str], start: Path | None = None, clock: Clock | None = None) -> int:
    start = start or Path.cwd()
    clock = clock or SystemClock()

    try:
        target, rest = _extract_flag(argv, ("-w", "--workstream"), "a workstream slug")
        opt_type, rest = _extract_flag(rest, ("-t", "--type"), "a type")
        opt_context, rest = _extract_flag(rest, ("-c", "--context"), "a context")
        opt_tag, rest = _extract_flag(rest, ("-g", "--tag"), "a tag")
    except ValueError as exc:
        print(f"lume: {exc}\n{USAGE}", file=sys.stderr)
        return 2

    cmd = rest[1] if len(rest) > 1 else "status"
    if cmd not in (
        "status", "new", "open", "close", "reopen", "snapshot", "migrate",
        "entities", "schema", "get", "plan", "decide", "retro",
        *TRANSITIONS,
    ):
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
    if cmd == "schema" and not arg:
        print('lume: usage: lume schema <entity>', file=sys.stderr)
        return 2
    if cmd == "decide" and not arg:
        print('lume: usage: lume decide [-c <context>] "<decision>" ["<rationale>"]',
              file=sys.stderr)
        return 2
    if cmd == "reopen" and not arg:
        print('lume: usage: lume reopen <slug>', file=sys.stderr)
        return 2

    # Backing selection happens once, here at the edge (decision F5): LUME_BACKING
    # picks the TrackingStore; no engine code below branches on it. fs is default.
    backing = os.environ.get("LUME_BACKING", "fs").strip().lower()
    store = None
    if backing not in ("fs", ""):
        lume_dir = Repository(start, clock).find_lume_dir()
        if lume_dir is None:
            print("lume: no .lume/ found from here.", file=sys.stderr)
            return 1
        if backing == "sqlite":
            store = SQLiteStore(lume_dir / "lume.db")
        else:
            print(f"lume: unknown LUME_BACKING '{backing}' (use 'fs' or 'sqlite').",
                  file=sys.stderr)
            return 2
    repo = Repository(start, clock, store=store)

    # `new` names its workstream positionally; it needs no target resolution.
    if cmd == "new":
        try:
            ws = repo.create_workstream(arg, rest[3].strip())
        except LumeError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"created workstream '{ws.name}' (active): {ws.name}/objective.json")
        print('next: edit its objective.json, then: lume open "<first iteration>".')
        return 0

    # `reopen` targets a specific (closed) workstream by slug, bypassing the
    # closed-workstream gate in the normal resolver.
    if cmd == "reopen":
        try:
            ws = repo.reopen_workstream(arg)
        except LumeError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"reopened workstream '{ws.name}' (active).")
        return 0

    # `migrate` acts on every workstream under .lume/, not a single target.
    if cmd == "migrate":
        lume_dir = repo.find_lume_dir()
        if lume_dir is None:
            print("lume: no .lume/ found from here.", file=sys.stderr)
            return 1
        written = migrate_mod.migrate_all(repo, lume_dir)
        for slug in written:
            print(f"migrated: {slug}/state.json")
        print(f"migrate: wrote {len(written)} state.json file(s).")
        return 0

    # Discovery verbs that need no workstream target.
    if cmd == "entities":
        for kind in entity_kinds():
            print(kind)
        return 0

    if cmd == "schema":
        try:
            schema = load_schema(arg)
        except SchemaError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        _json_out(schema)
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
        # JSON-only: derive the snapshot from state and print it; nothing persisted.
        print(ws.derive_snapshot().rstrip())
        return 0

    if cmd == "open":
        try:
            iteration = ws.open_iteration(arg, type=opt_type or DEFAULT_TYPE)
        except GateError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"opened iteration {iteration.id:03d}, phase {iteration.phase}: "
              f"{ws.name}/iterations/{iteration.id:03d}.json")
        print("next: draft its DoD, then have the operator approve before work starts.")
        return 0

    if cmd == "get":
        doc = ws.state_doc
        # 'plan' is a friendly alias for the plan_item entity.
        entity = "plan_item" if arg == "plan" else arg
        id_arg = rest[3].strip() if len(rest) > 3 else ""

        if not entity:
            _json_out(doc)
            return 0

        if entity not in _ENTITY_KEY:
            kinds = ", ".join(sorted(_ENTITY_KEY))
            print(f"lume: unknown entity '{entity}'. Known: {kinds}.", file=sys.stderr)
            return 1

        value = doc[_ENTITY_KEY[entity]]

        if not id_arg:
            _json_out(value)
            return 0

        if entity == "workstream":
            print("lume: 'workstream' is a single entity; no id selector.", file=sys.stderr)
            return 1

        if entity == "iteration":
            try:
                target_id: object = int(id_arg.lstrip("0") or "0")
            except ValueError:
                print(f"lume: iteration id must be an integer, got '{id_arg}'.", file=sys.stderr)
                return 1
        else:
            target_id = id_arg

        found = next((e for e in value if e["id"] == target_id), None)
        if found is None:
            print(f"lume: {entity} '{id_arg}' not found.", file=sys.stderr)
            return 1
        _json_out(found)
        return 0

    if cmd == "plan":
        sub = arg  # rest[2]
        if sub not in ("add", "link"):
            print('lume: usage: lume plan <add|link> ...', file=sys.stderr)
            return 2

        if sub == "add":
            sketch = rest[3].strip() if len(rest) > 3 else ""
            if not sketch:
                print('lume: usage: lume plan add [-t type] [-g tag] "<sketch>"',
                      file=sys.stderr)
                return 2
            tag = opt_tag or "committed"
            if tag not in ("committed", "optional"):
                print(f"lume: tag must be 'committed' or 'optional', got '{tag}'.",
                      file=sys.stderr)
                return 2
            item = ws.add_plan_item(
                sketch=sketch,
                type=opt_type or "execution",
                tag=tag,
            )
            print(f"plan add: {item.id} ({item.type}, {item.tag}): {item.sketch}")
            return 0

        # sub == "link"
        plan_id = rest[3].strip() if len(rest) > 3 else ""
        iter_arg = rest[4].strip() if len(rest) > 4 else ""
        if not plan_id or not iter_arg:
            print('lume: usage: lume plan link <plan-id> <iter-id>', file=sys.stderr)
            return 2
        try:
            iter_id = int(iter_arg.lstrip("0") or "0")
        except ValueError:
            print(f"lume: iter-id must be an integer, got '{iter_arg}'.", file=sys.stderr)
            return 2
        try:
            item = ws.link_plan_item(plan_id, iter_id)
        except GateError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"plan link: {item.id} -> iter {item.iter:03d}")
        return 0

    if cmd == "decide":
        rationale = rest[3].strip() if len(rest) > 3 else ""
        entry = ws.add_decision(arg, context=opt_context or "", rationale=rationale)
        print(f"decide: logged {entry['date']} | {entry['decision']}")
        return 0

    if cmd == "retro":
        retro = ws.retro_doc()
        existed = retro is not None
        if not existed:
            retro = {"overall_verdict": "(draft: fill in the verdict)", "carry_forwards": []}
        try:
            ws.save_retro(retro)
        except SchemaError as exc:
            print(f"lume: {exc}", file=sys.stderr)
            return 1
        print(f"retro: {'updated' if existed else 'created'} retro.json")
        return 0

    # cmd is a transition verb
    try:
        iteration = ws.transition(cmd, note=arg or None)
    except GateError as exc:
        print(f"lume: {exc}", file=sys.stderr)
        return 1
    print(f"{cmd}: iteration {iteration.id:03d} -> phase {iteration.phase}")
    return 0
