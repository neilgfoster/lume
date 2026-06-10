"""Content-authoring verb handlers: plan, decide, retro.

Each is `handle_<verb>(ctx) -> int`, owning its arg validation, action, output.
"""
from __future__ import annotations

from ..context import Context


def handle_plan(ctx: Context) -> int:
    sub = ctx.arg
    if sub not in ("add", "link"):
        ctx.fail("usage", "usage: lume plan <add|link> ...")
        return 2
    ws = ctx.require_ws()

    if sub == "add":
        sketch = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
        if not sketch:
            ctx.fail("usage", 'usage: lume plan add [-t type] [-g tag] "<sketch>"')
            return 2
        tag = ctx.opt_tag or "committed"
        if tag not in ("committed", "optional"):
            ctx.fail("usage", f"tag must be 'committed' or 'optional', got '{tag}'.")
            return 2
        item = ws.add_plan_item(sketch=sketch, type=ctx.opt_type or "execution", tag=tag)
        ctx.ok({"result": "plan_add", "id": item.id, "type": item.type,
                "tag": item.tag, "sketch": item.sketch},
               f"plan add: {item.id} ({item.type}, {item.tag}): {item.sketch}")
        return 0

    # sub == "link"
    plan_id = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
    iter_arg = ctx.rest[4].strip() if len(ctx.rest) > 4 else ""
    if not plan_id or not iter_arg:
        ctx.fail("usage", "usage: lume plan link <plan-id> <iter-id>")
        return 2
    try:
        iter_id = int(iter_arg.lstrip("0") or "0")
    except ValueError:
        ctx.fail("usage", f"iter-id must be an integer, got '{iter_arg}'.")
        return 2
    item = ws.link_plan_item(plan_id, iter_id)  # GateError -> dispatch maps to exit 1
    ctx.ok({"result": "plan_link", "id": item.id, "iter": item.iter},
           f"plan link: {item.id} -> iter {item.iter:03d}")
    return 0


def handle_decide(ctx: Context) -> int:
    if not ctx.arg:
        ctx.fail("usage", 'usage: lume decide [-c <context>] "<decision>" ["<rationale>"]')
        return 2
    ws = ctx.require_ws()
    rationale = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
    entry = ws.add_decision(ctx.arg, context=ctx.opt_context or "", rationale=rationale)
    ctx.ok({"result": "decide", "date": entry["date"], "decision": entry["decision"]},
           f"decide: logged {entry['date']} | {entry['decision']}")
    return 0


def handle_retro(ctx: Context) -> int:
    ws = ctx.require_ws()
    retro = ws.retro_doc()
    existed = retro is not None
    if not existed:
        retro = {"overall_verdict": "(draft: fill in the verdict)", "carry_forwards": []}
    ws.save_retro(retro)  # SchemaError -> dispatch maps to exit 1
    verb = "updated" if existed else "created"
    ctx.ok({"result": "retro", "status": verb}, f"retro: {verb} retro.json")
    return 0
