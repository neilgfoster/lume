"""CLI dispatch. Pure wiring: build the Repository from injected start/clock,
route the command, map errors to messages + exit codes. No domain logic here.

A workstream is selected with `-w <slug>` (alias `--workstream`), which may
appear anywhere in the args. Omitted, commands default to the sole active
workstream. `lume status` with no target is the cross-workstream review queue.

Grammar (agent-friendly, stable):
  lume [--json] [-w <slug>] <verb> [positional args...] [flags...]
- Verb first; global flags (--json, -w/--workstream) and value flags (-t/--type,
  -c/--context, -g/--tag) may appear anywhere. Positionals are verb-specific.
- Discovery: `lume verbs` lists all verbs (the catalog); `lume verbs <name>`
  describes one; `lume entities` + `lume schema <entity>` cover the data shapes;
  `lume get` returns state as JSON. Every verb advertises its args as data in
  the catalog `inputs` (the MCP inputSchema analogue).
- Output: human text by default; with --json, every verb emits one structured
  result object on stdout and errors emit {"error": {"code", "message"}} on stderr.
- Exit codes: 0 ok; 1 domain/gate error; 2 usage error. These are the primary,
  stable signal and are identical with or without --json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import migrate as migrate_mod
from .clock import Clock, SystemClock
from .errors import GateError, LumeError, NoLumeDirError, NoWorkstreamError, SchemaError
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

# The verb catalog - the single source of truth for what the CLI offers. Drives
# `lume verbs` (the discovery surface), dispatch membership, and USAGE, so there
# is no second hardcoded verb list to drift. Each entry: name, summary, args
# (human outline) and inputs (structured arg schema - the MCP inputSchema analogue).


def _pos(name: str, required: bool, description: str) -> dict:
    return {"name": name, "kind": "positional", "required": required, "description": description}


# Shared flag inputs (the flags the parser actually accepts).
_F_JSON = {"name": "json", "kind": "flag", "flag": "--json", "required": False,
           "description": "Emit machine-readable JSON output and errors."}
_F_W = {"name": "workstream", "kind": "flag", "flag": "-w/--workstream", "required": False,
        "description": "Target workstream slug (defaults to the sole active one)."}
_F_TYPE = {"name": "type", "kind": "flag", "flag": "-t/--type", "required": False,
           "description": "Iteration / plan-item type."}
_F_CONTEXT = {"name": "context", "kind": "flag", "flag": "-c/--context", "required": False,
              "description": "Free-text context tag."}
_F_TAG = {"name": "tag", "kind": "flag", "flag": "-g/--tag", "required": False,
          "description": "Plan-item tag: committed | optional."}


def _verb(name: str, summary: str, args: str, inputs: list[dict], scoped: bool) -> dict:
    """Build a catalog entry; `scoped` verbs accept -w; all verbs accept --json."""
    ins = list(inputs) + ([_F_W] if scoped else []) + [_F_JSON]
    return {"name": name, "summary": summary, "args": args, "inputs": ins}


_CATALOG: list[dict] = [
    _verb("status", "Review queue (no -w), or one workstream's detail (-w).", "[-w <slug>]", [], True),
    _verb("verbs", "List every verb, or describe one by name.", "[<verb>]",
          [_pos("verb", False, "Show only this verb's catalog entry.")], False),
    _verb("new", "Create a new workstream.", "<slug> \"<title>\"",
          [_pos("slug", True, "New workstream slug."), _pos("title", True, "Objective title.")], False),
    _verb("open", "Open the next iteration.", "[-t <type>] \"<title>\"",
          [_pos("title", True, "Iteration title."), _F_TYPE], True),
    _verb("close", "Close the current workstream.", "", [], True),
    _verb("reopen", "Reopen a closed workstream.", "<slug>",
          [_pos("slug", True, "Workstream slug to reopen.")], False),
    _verb("snapshot", "Print the derived Done/Now/Next snapshot.", "", [], True),
    _verb("migrate", "Migrate legacy markdown workstreams to JSON.", "", [], False),
    _verb("entities", "List the entity kinds.", "", [], False),
    _verb("schema", "Print an entity's JSON Schema.", "<entity>",
          [_pos("entity", True, "Entity kind (see `lume entities`).")], False),
    _verb("get", "Fetch state as JSON (optionally an entity / id).", "[<entity> [<id>]]",
          [_pos("entity", False, "Entity kind or 'plan'."), _pos("id", False, "Entity id.")], True),
    _verb("plan", "Add or link a plan item.",
          "add [-t type] [-g tag] \"<sketch>\" | link <plan-id> <iter-id>",
          [_pos("subcommand", True, "add | link."),
           _pos("sketch_or_plan_id", False, "add: the sketch; link: the plan id."),
           _pos("iter_id", False, "link: the iteration id."), _F_TYPE, _F_TAG], True),
    _verb("decide", "Log a decision.", "[-c <context>] \"<decision>\" [\"<rationale>\"]",
          [_pos("decision", True, "The decision."), _pos("rationale", False, "Why."), _F_CONTEXT], True),
    _verb("retro", "Create or refresh the retro artifact.", "", [], True),
    *(
        _verb(v, f"Transition the current iteration: {src} -> {dst}.",
              "\"<reason>\"" if v == "reject" else "",
              [_pos("reason", True, "Rejection reason.")] if v == "reject" else [], True)
        for v, (src, dst) in TRANSITIONS.items()
    ),
]
_VERB_NAMES = tuple(e["name"] for e in _CATALOG)
_VERBS = " ".join(_VERB_NAMES)
USAGE = f'lume: usage: lume [--json] [-w <slug>] <{_VERBS}>   (new/open/reject take an argument)'


def _extract_bool_flag(argv: list[str], name: str) -> tuple[bool, list[str]]:
    """Pull a valueless flag (e.g. --json) out of argv (anywhere); argv[0] preserved."""
    present = name in argv[1:]
    rest = [argv[0]] + [t for t in argv[1:] if t != name] if argv else []
    return present, rest


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


def _iteration_summary(it) -> dict | None:
    if it is None:
        return None
    return {"id": it.id, "type": it.type, "phase": it.phase}


def _detail_data(ws: Workstream) -> dict:
    """Single-workstream status as a structured object (the --json form of _render_detail)."""
    return {
        "name": ws.name,
        "status": ws.status,
        "objective": ws.objective_line(),
        "current_iteration": _iteration_summary(ws.current_iteration()),
    }


def _queue_data(workstreams: list[Workstream]) -> dict:
    """Cross-workstream review queue as a structured object (the --json form of _render_queue)."""
    awaiting, in_progress, closed = [], [], []
    for ws in workstreams:
        if ws.is_closed:
            closed.append(ws.name)
            continue
        it = ws.current_iteration()
        entry = {"workstream": ws.name, "iteration": _iteration_summary(it)}
        if it is not None and it.phase == "handback":
            awaiting.append(entry)
        else:
            in_progress.append(entry)
    return {"awaiting": awaiting, "in_progress": in_progress, "closed": closed}


def _json_out(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str], start: Path | None = None, clock: Clock | None = None) -> int:
    start = start or Path.cwd()
    clock = clock or SystemClock()

    # --json is parsed first so error formatting honours it even on flag errors.
    json_mode, argv = _extract_bool_flag(argv, "--json")

    try:
        target, rest = _extract_flag(argv, ("-w", "--workstream"), "a workstream slug")
        opt_type, rest = _extract_flag(rest, ("-t", "--type"), "a type")
        opt_context, rest = _extract_flag(rest, ("-c", "--context"), "a context")
        opt_tag, rest = _extract_flag(rest, ("-g", "--tag"), "a tag")
    except ValueError as exc:
        _fail(json_mode, "usage", str(exc))
        if not json_mode:
            print(USAGE, file=sys.stderr)
        return 2

    cmd = rest[1] if len(rest) > 1 else "status"
    if cmd not in _VERB_NAMES:
        _fail(json_mode, "usage", f"unknown command '{cmd}'.")
        if not json_mode:
            print(USAGE, file=sys.stderr)
        return 2

    # Parse per-command positional arguments before touching the filesystem.
    arg = rest[2].strip() if len(rest) > 2 else ""
    if cmd == "open" and not arg:
        _fail(json_mode, "usage", 'usage: lume open "<title>"')
        return 2
    if cmd == "reject" and not arg:
        _fail(json_mode, "usage", 'usage: lume reject "<reason>"  (a reason is required)')
        return 2
    if cmd == "new" and (not arg or not (len(rest) > 3 and rest[3].strip())):
        _fail(json_mode, "usage", 'usage: lume new <slug> "<title>"')
        return 2
    if cmd == "schema" and not arg:
        _fail(json_mode, "usage", "usage: lume schema <entity>")
        return 2
    if cmd == "decide" and not arg:
        _fail(json_mode, "usage", 'usage: lume decide [-c <context>] "<decision>" ["<rationale>"]')
        return 2
    if cmd == "reopen" and not arg:
        _fail(json_mode, "usage", "usage: lume reopen <slug>")
        return 2

    # Backing selection happens once, here at the edge (decision F5): LUME_BACKING
    # picks the TrackingStore; no engine code below branches on it. fs is default.
    backing = os.environ.get("LUME_BACKING", "fs").strip().lower()
    store = None
    if backing not in ("fs", ""):
        lume_dir = Repository(start, clock).find_lume_dir()
        if lume_dir is None:
            _fail(json_mode, "no_lume_dir", "no .lume/ found from here.")
            return 1
        if backing == "sqlite":
            store = SQLiteStore(lume_dir / "lume.db")
        else:
            _fail(json_mode, "usage", f"unknown LUME_BACKING '{backing}' (use 'fs' or 'sqlite').")
            return 2
    repo = Repository(start, clock, store=store)

    # `new` names its workstream positionally; it needs no target resolution.
    if cmd == "new":
        try:
            ws = repo.create_workstream(arg, rest[3].strip())
        except LumeError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        _ok(json_mode,
            {"result": "new", "workstream": ws.name, "status": "active"},
            f"created workstream '{ws.name}' (active): {ws.name}/objective.json",
            'next: edit its objective.json, then: lume open "<first iteration>".')
        return 0

    # `reopen` targets a specific (closed) workstream by slug, bypassing the
    # closed-workstream gate in the normal resolver.
    if cmd == "reopen":
        try:
            ws = repo.reopen_workstream(arg)
        except LumeError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        _ok(json_mode,
            {"result": "reopen", "workstream": ws.name, "status": "active"},
            f"reopened workstream '{ws.name}' (active).")
        return 0

    # `migrate` acts on every workstream under .lume/, not a single target.
    if cmd == "migrate":
        lume_dir = repo.find_lume_dir()
        if lume_dir is None:
            _fail(json_mode, "no_lume_dir", "no .lume/ found from here.")
            return 1
        written = migrate_mod.migrate_all(repo, lume_dir)
        if json_mode:
            _json_out({"migrated": written, "count": len(written)})
            return 0
        for slug in written:
            print(f"migrated: {slug}/state.json")
        print(f"migrate: wrote {len(written)} state.json file(s).")
        return 0

    # Discovery verbs that need no workstream target.
    if cmd == "verbs":
        if arg:  # single-verb lookup
            entry = next((e for e in _CATALOG if e["name"] == arg), None)
            if entry is None:
                _fail(json_mode, "not_found", f"unknown verb '{arg}'.")
                return 1
            if json_mode:
                _json_out(entry)
                return 0
            print(f"{entry['name']}  -  {entry['summary']}")
            print(f"usage: lume [--json] [-w <slug>] {entry['name']} {entry['args']}".rstrip())
            for i in entry["inputs"]:
                token = i["flag"] if i["kind"] == "flag" else f"<{i['name']}>"
                req = "" if i["required"] else " (optional)"
                print(f"  {token}{req}: {i['description']}")
            return 0
        if json_mode:
            _json_out(_CATALOG)
            return 0
        width = max(len(e["name"]) for e in _CATALOG)
        for e in _CATALOG:
            print(f"{e['name']:<{width}}  {e['summary']}")
        return 0

    if cmd == "entities":
        if json_mode:
            _json_out(entity_kinds())
            return 0
        for kind in entity_kinds():
            print(kind)
        return 0

    if cmd == "schema":
        try:
            schema = load_schema(arg)
        except SchemaError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        _json_out(schema)
        return 0

    # `status` with no target is the cross-workstream queue.
    if cmd == "status" and target is None:
        lume_dir = repo.find_lume_dir()
        if lume_dir is None:
            _fail(json_mode, "no_lume_dir", "no .lume/ found from here.")
            return 1
        workstreams = repo.workstreams(lume_dir)
        if json_mode:
            _json_out(_queue_data(workstreams))
            return 0
        _render_queue(workstreams)
        return 0

    # Everything else acts on one workstream: target via -w, else sole active.
    try:
        ws = repo.workstream(target)
    except LumeError as exc:
        _fail(json_mode, _code_for(exc), str(exc))
        return 1

    if cmd == "status":
        if json_mode:
            _json_out(_detail_data(ws))
            return 0
        _render_detail(ws)
        return 0

    if cmd == "close":
        ws.set_status(CLOSED)
        _ok(json_mode,
            {"result": "close", "workstream": ws.name, "status": "closed"},
            f"closed workstream '{ws.name}'.")
        return 0

    if cmd == "snapshot":
        # JSON-only: derive the snapshot from state and print it; nothing persisted.
        if json_mode:
            _json_out({"snapshot": ws.derive_snapshot().rstrip()})
            return 0
        print(ws.derive_snapshot().rstrip())
        return 0

    if cmd == "open":
        try:
            iteration = ws.open_iteration(arg, type=opt_type or DEFAULT_TYPE)
        except GateError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        _ok(json_mode,
            {"result": "open", "workstream": ws.name, "iteration": iteration.id,
             "phase": iteration.phase, "type": iteration.type},
            f"opened iteration {iteration.id:03d}, phase {iteration.phase}: "
            f"{ws.name}/iterations/{iteration.id:03d}.json",
            "next: draft its DoD, then have the operator approve before work starts.")
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
            _fail(json_mode, "not_found", f"unknown entity '{entity}'. Known: {kinds}.")
            return 1

        value = doc[_ENTITY_KEY[entity]]

        if not id_arg:
            _json_out(value)
            return 0

        if entity == "workstream":
            _fail(json_mode, "usage", "'workstream' is a single entity; no id selector.")
            return 1

        if entity == "iteration":
            try:
                target_id: object = int(id_arg.lstrip("0") or "0")
            except ValueError:
                _fail(json_mode, "usage", f"iteration id must be an integer, got '{id_arg}'.")
                return 1
        else:
            target_id = id_arg

        found = next((e for e in value if e["id"] == target_id), None)
        if found is None:
            _fail(json_mode, "not_found", f"{entity} '{id_arg}' not found.")
            return 1
        _json_out(found)
        return 0

    if cmd == "plan":
        sub = arg  # rest[2]
        if sub not in ("add", "link"):
            _fail(json_mode, "usage", "usage: lume plan <add|link> ...")
            return 2

        if sub == "add":
            sketch = rest[3].strip() if len(rest) > 3 else ""
            if not sketch:
                _fail(json_mode, "usage", 'usage: lume plan add [-t type] [-g tag] "<sketch>"')
                return 2
            tag = opt_tag or "committed"
            if tag not in ("committed", "optional"):
                _fail(json_mode, "usage", f"tag must be 'committed' or 'optional', got '{tag}'.")
                return 2
            item = ws.add_plan_item(
                sketch=sketch,
                type=opt_type or "execution",
                tag=tag,
            )
            _ok(json_mode,
                {"result": "plan_add", "id": item.id, "type": item.type,
                 "tag": item.tag, "sketch": item.sketch},
                f"plan add: {item.id} ({item.type}, {item.tag}): {item.sketch}")
            return 0

        # sub == "link"
        plan_id = rest[3].strip() if len(rest) > 3 else ""
        iter_arg = rest[4].strip() if len(rest) > 4 else ""
        if not plan_id or not iter_arg:
            _fail(json_mode, "usage", "usage: lume plan link <plan-id> <iter-id>")
            return 2
        try:
            iter_id = int(iter_arg.lstrip("0") or "0")
        except ValueError:
            _fail(json_mode, "usage", f"iter-id must be an integer, got '{iter_arg}'.")
            return 2
        try:
            item = ws.link_plan_item(plan_id, iter_id)
        except GateError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        _ok(json_mode,
            {"result": "plan_link", "id": item.id, "iter": item.iter},
            f"plan link: {item.id} -> iter {item.iter:03d}")
        return 0

    if cmd == "decide":
        rationale = rest[3].strip() if len(rest) > 3 else ""
        entry = ws.add_decision(arg, context=opt_context or "", rationale=rationale)
        _ok(json_mode,
            {"result": "decide", "date": entry["date"], "decision": entry["decision"]},
            f"decide: logged {entry['date']} | {entry['decision']}")
        return 0

    if cmd == "retro":
        retro = ws.retro_doc()
        existed = retro is not None
        if not existed:
            retro = {"overall_verdict": "(draft: fill in the verdict)", "carry_forwards": []}
        try:
            ws.save_retro(retro)
        except SchemaError as exc:
            _fail(json_mode, _code_for(exc), str(exc))
            return 1
        verb = "updated" if existed else "created"
        _ok(json_mode,
            {"result": "retro", "status": verb},
            f"retro: {verb} retro.json")
        return 0

    # cmd is a transition verb
    try:
        iteration = ws.transition(cmd, note=arg or None)
    except GateError as exc:
        _fail(json_mode, _code_for(exc), str(exc))
        return 1
    _ok(json_mode,
        {"result": cmd, "workstream": ws.name, "iteration": iteration.id,
         "phase": iteration.phase},
        f"{cmd}: iteration {iteration.id:03d} -> phase {iteration.phase}")
    return 0
