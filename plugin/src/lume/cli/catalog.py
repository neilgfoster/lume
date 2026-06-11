"""The verb catalog - the single source of truth for what the CLI offers.

Drives `lume verbs` (the discovery surface), dispatch membership, and USAGE, so
there is no second hardcoded verb list to drift. Each entry: name, summary, args
(human outline) and inputs (structured arg schema - the MCP inputSchema analogue).
"""
from __future__ import annotations

from ..iteration import TRANSITIONS


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
    _verb("spawn", "Create a child workstream of the -w target.", "<slug> \"<title>\"",
          [_pos("slug", True, "New child workstream slug."),
           _pos("title", True, "Child objective title.")], True),
    _verb("close", "Close the current workstream.", "", [], True),
    _verb("reopen", "Reopen a closed workstream.", "<slug>",
          [_pos("slug", True, "Workstream slug to reopen.")], False),
    _verb("snapshot", "Print the derived Done/Now/Next snapshot.", "", [], True),
    _verb("check", "Dry-run the current iteration's DoD machine-checks (read-only).", "", [], True),
    _verb("gap", "Record, list, scan, or resolve cross-repo capability gaps.",
          "add \"<title>\" [-c <context>] | list | scan | resolve <source> <id>",
          [_pos("subcommand", True, "add | list | scan | resolve."),
           _pos("arg", False, "add: title; resolve: source then id."), _F_CONTEXT], False),
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
    _verb("seed", "Bootstrap the seed workstream with a mode-specific discovery iteration.",
          "[--new | --existing]",
          [{"name": "new", "kind": "flag", "flag": "--new", "required": False,
            "description": "Treat the project as new (why/scope/constraints DoD)."},
           {"name": "existing", "kind": "flag", "flag": "--existing", "required": False,
            "description": "Treat the project as existing (repo map DoD)."}], False),
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
