"""Verb handlers, grouped by concern, assembled into the dispatch registry.

- lifecycle:  new, reopen, close, open, migrate, (transitions)
- discovery:  verbs, entities, schema, status, get, snapshot
- authoring:  plan, decide, retro

`HANDLERS` maps a verb name to its handler; transition verbs are not in it -
app.main falls back to `handle_transition`. Adding a verb is local: write its
handler in the right group module and add one HANDLERS row here.
"""
from __future__ import annotations

from .authoring import handle_decide, handle_plan, handle_retro
from .discovery import (
    handle_check,
    handle_entities,
    handle_get,
    handle_schema,
    handle_snapshot,
    handle_status,
    handle_verbs,
)
from .lifecycle import (
    handle_close,
    handle_migrate,
    handle_new,
    handle_open,
    handle_reopen,
    handle_seed,
    handle_transition,
)

HANDLERS = {
    "seed": handle_seed,
    "new": handle_new,
    "reopen": handle_reopen,
    "migrate": handle_migrate,
    "verbs": handle_verbs,
    "entities": handle_entities,
    "schema": handle_schema,
    "status": handle_status,
    "close": handle_close,
    "snapshot": handle_snapshot,
    "check": handle_check,
    "open": handle_open,
    "get": handle_get,
    "plan": handle_plan,
    "decide": handle_decide,
    "retro": handle_retro,
}

__all__ = ["HANDLERS", "handle_transition"]
