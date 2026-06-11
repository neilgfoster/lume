"""CLI dispatch. Pure wiring: parse flags, select the backing, build a Context,
route to the verb's handler, map domain errors to exit codes. No domain logic here.

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

Each verb's parse/action/output lives in its handler in handlers.py; the catalog
(catalog.py) is the single source of truth for which verbs exist.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from ..clock import Clock, SystemClock
from ..errors import LumeError
from ..repository import Repository
from ..store import SQLiteStore
from .catalog import _VERB_NAMES, USAGE
from .context import Context
from .flags import _extract_bool_flag, _extract_flag, _extract_multi_flag
from .handlers import HANDLERS, handle_transition
from .io import _code_for, _fail


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
        opt_new, rest = _extract_bool_flag(rest, "--new")
        opt_existing, rest = _extract_bool_flag(rest, "--existing")
        opt_spawn, rest = _extract_bool_flag(rest, "--spawn")
        opt_charter, rest = _extract_multi_flag(rest, ("--charter",), "a file glob")
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

    # Backing selection happens once, here at the edge (decision F5): LUME_BACKING
    # picks the TrackingStore; no handler below branches on it. fs is default.
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

    ctx = Context(
        repo=Repository(start, clock, store=store),
        cmd=cmd,
        rest=rest,
        arg=rest[2].strip() if len(rest) > 2 else "",
        json_mode=json_mode,
        target=target,
        opt_type=opt_type,
        opt_context=opt_context,
        opt_tag=opt_tag,
        opt_new=opt_new,
        opt_existing=opt_existing,
        opt_spawn=opt_spawn,
        opt_charter=opt_charter,
    )

    handler = HANDLERS.get(cmd, handle_transition)
    try:
        return handler(ctx)
    except LumeError as exc:
        _fail(json_mode, _code_for(exc), str(exc))
        return 1
