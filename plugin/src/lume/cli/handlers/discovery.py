"""Discovery/read verb handlers: verbs, entities, schema, status, get, snapshot.

All read-only views and queries; each is `handle_<verb>(ctx) -> int`.
"""
from __future__ import annotations

from ...dod_checks import evaluate_dod
from ...validate import entity_kinds, load_schema
from ..catalog import _CATALOG
from ..context import Context
from ..io import _detail_data, _queue_data, _render_detail, _render_queue

# Entity kind -> state doc key (for `lume get`).
_ENTITY_KEY = {
    "workstream": "workstream",
    "iteration": "iterations",
    "plan_item": "plan",
}


def handle_verbs(ctx: Context) -> int:
    if ctx.arg:  # single-verb lookup
        entry = next((e for e in _CATALOG if e["name"] == ctx.arg), None)
        if entry is None:
            ctx.fail("not_found", f"unknown verb '{ctx.arg}'.")
            return 1
        if ctx.json_mode:
            ctx.out(entry)
            return 0
        print(f"{entry['name']}  -  {entry['summary']}")
        print(f"usage: lume [--json] [-w <slug>] {entry['name']} {entry['args']}".rstrip())
        for i in entry["inputs"]:
            token = i["flag"] if i["kind"] == "flag" else f"<{i['name']}>"
            req = "" if i["required"] else " (optional)"
            print(f"  {token}{req}: {i['description']}")
        return 0
    if ctx.json_mode:
        ctx.out(_CATALOG)
        return 0
    width = max(len(e["name"]) for e in _CATALOG)
    for e in _CATALOG:
        print(f"{e['name']:<{width}}  {e['summary']}")
    return 0


def handle_entities(ctx: Context) -> int:
    if ctx.json_mode:
        ctx.out(entity_kinds())
        return 0
    for kind in entity_kinds():
        print(kind)
    return 0


def handle_schema(ctx: Context) -> int:
    if not ctx.arg:
        ctx.fail("usage", "usage: lume schema <entity>")
        return 2
    ctx.out(load_schema(ctx.arg))  # SchemaError -> dispatch maps to exit 1
    return 0


def handle_status(ctx: Context) -> int:
    if ctx.target is None:  # cross-workstream queue
        lume_dir = ctx.repo.find_lume_dir()
        if lume_dir is None:
            ctx.fail("no_lume_dir", "no .lume/ found from here.")
            return 1
        workstreams = ctx.repo.workstreams(lume_dir)
        if ctx.json_mode:
            ctx.out(_queue_data(workstreams))
            return 0
        _render_queue(workstreams)
        return 0
    ws = ctx.require_ws()
    children = ctx.repo.children(ws.id)
    if ctx.json_mode:
        ctx.out(_detail_data(ws, children))
        return 0
    _render_detail(ws, children)
    return 0


def handle_snapshot(ctx: Context) -> int:
    ws = ctx.require_ws()
    if ctx.json_mode:
        ctx.out({"snapshot": ws.derive_snapshot().rstrip()})
        return 0
    print(ws.derive_snapshot().rstrip())
    return 0


def handle_get(ctx: Context) -> int:
    ws = ctx.require_ws()
    doc = ws.state_doc
    # 'plan' is a friendly alias for the plan_item entity.
    entity = "plan_item" if ctx.arg == "plan" else ctx.arg
    id_arg = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""

    if not entity:
        ctx.out(doc)
        return 0

    if entity not in _ENTITY_KEY:
        kinds = ", ".join(sorted(_ENTITY_KEY))
        ctx.fail("not_found", f"unknown entity '{entity}'. Known: {kinds}.")
        return 1

    value = doc[_ENTITY_KEY[entity]]

    if not id_arg:
        ctx.out(value)
        return 0

    if entity == "workstream":
        ctx.fail("usage", "'workstream' is a single entity; no id selector.")
        return 1

    if entity == "iteration":
        try:
            target_id: object = int(id_arg.lstrip("0") or "0")
        except ValueError:
            ctx.fail("usage", f"iteration id must be an integer, got '{id_arg}'.")
            return 1
    else:
        target_id = id_arg

    found = next((e for e in value if e["id"] == target_id), None)
    if found is None:
        ctx.fail("not_found", f"{entity} '{id_arg}' not found.")
        return 1
    ctx.out(found)
    return 0


def handle_check(ctx: Context) -> int:
    """Dry-run the current iteration's DoD checks (read-only; no transition).

    Runs the same evaluator the accept veto uses, but never mutates state.
    Exit 0 when no verifiable check fails, 1 when any does - so it doubles as a
    pre-accept gate an operator (human or autonomous) can read first. Under
    --json, emits the structured per-item results (the machine-readable list).
    """
    ws = ctx.require_ws()
    it = ws.current_iteration()
    content = ws.current_iteration_content()
    if it is None or content is None:
        ctx.fail("not_found", "no current iteration to check.")
        return 1
    results = evaluate_dod(content, ctx.repo.project_root())
    failed = [r for r in results if r["verifiable"] and not r["passed"]]
    if ctx.json_mode:
        ctx.out({"iteration": it.id, "failed": len(failed), "results": results})
        return 0 if not failed else 1
    for r in results:
        mark = "prose" if not r["verifiable"] else ("PASS" if r["passed"] else "FAIL")
        print(f"[{mark}] {r['text']} - {r['reason']}")
    print(f"{len(failed)} failed / {len(results)} items (iteration {it.id:03d})")
    return 0 if not failed else 1
