"""Lifecycle verb handlers: creating, opening, transitioning, closing, migrating.

Each handler is `handle_<verb>(ctx) -> int`, owning its arg validation (return 2
on a usage error), action, and output. Domain failures raise a LumeError that
app.main's dispatch maps to a structured error + exit 1.
"""
from __future__ import annotations

from ... import migrate as migrate_mod
from ...iteration import DEFAULT_TYPE
from ...workstream import CLOSED
from ..context import Context


def handle_new(ctx: Context) -> int:
    if not ctx.arg or not (len(ctx.rest) > 3 and ctx.rest[3].strip()):
        ctx.fail("usage", 'usage: lume new <slug> "<title>"')
        return 2
    ws = ctx.repo.create_workstream(ctx.arg, ctx.rest[3].strip())
    ctx.ok({"result": "new", "id": ws.id, "workstream": ws.name, "status": "active"},
           f"created workstream '{ws.name}' [{ws.id}] (active): {ws.name}/objective.json",
           'next: edit its objective.json, then: lume open "<first iteration>".')
    return 0


def handle_reopen(ctx: Context) -> int:
    if not ctx.arg:
        ctx.fail("usage", "usage: lume reopen <slug>")
        return 2
    ws = ctx.repo.reopen_workstream(ctx.arg)
    ctx.ok({"result": "reopen", "id": ws.id, "workstream": ws.name, "status": "active"},
           f"reopened workstream '{ws.name}' (active).")
    return 0


def handle_close(ctx: Context) -> int:
    ws = ctx.require_ws()
    ws.set_status(CLOSED)
    ctx.ok({"result": "close", "id": ws.id, "workstream": ws.name, "status": "closed"},
           f"closed workstream '{ws.name}'.")
    return 0


def handle_open(ctx: Context) -> int:
    if not ctx.arg:
        ctx.fail("usage", 'usage: lume open "<title>"')
        return 2
    ws = ctx.require_ws()
    iteration = ws.open_iteration(ctx.arg, type=ctx.opt_type or DEFAULT_TYPE)
    ctx.ok({"result": "open", "workstream": ws.name, "iteration": iteration.id,
            "phase": iteration.phase, "type": iteration.type},
           f"opened iteration {iteration.id:03d}, phase {iteration.phase}: "
           f"{ws.name}/iterations/{iteration.id:03d}.json",
           "next: draft its DoD, then have the operator approve before work starts.")
    return 0


def handle_seed(ctx: Context) -> int:
    from ...seed import detect_mode, skeleton_for_mode

    if ctx.opt_new and ctx.opt_existing:
        ctx.fail("usage", "usage: lume seed [--new | --existing]")
        return 2

    # seed is the bootstrap verb: create .lume/ if this is a fresh repo.
    lume_dir = ctx.repo.ensure_lume_dir()

    if ctx.opt_new:
        mode = "new"
    elif ctx.opt_existing:
        mode = "existing"
    else:
        mode = detect_mode(lume_dir.parent)

    ws = ctx.repo.create_workstream("seed", "Seed", seed=True)
    title = "Seed: why, scope, constraints" if mode == "new" else "Seed: repo map"
    iteration = ws.open_iteration(title, type="discovery", skeleton=skeleton_for_mode(mode))
    ctx.ok(
        {"result": "seed", "id": ws.id, "workstream": ws.name, "mode": mode,
         "iteration": iteration.id},
        f"seeded '{ws.name}' [{ws.id}] ({mode}) with discovery iteration {iteration.id:03d}.",
        f"next: fill in the DoD, then: lume approve -w {ws.id}",
    )
    return 0


def handle_migrate(ctx: Context) -> int:
    lume_dir = ctx.repo.find_lume_dir()
    if lume_dir is None:
        ctx.fail("no_lume_dir", "no .lume/ found from here.")
        return 1
    written = migrate_mod.migrate_all(ctx.repo, lume_dir)
    if ctx.json_mode:
        ctx.out({"migrated": written, "count": len(written)})
        return 0
    for slug in written:
        print(f"migrated: {slug}/state.json")
    print(f"migrate: wrote {len(written)} state.json file(s).")
    return 0


def handle_transition(ctx: Context) -> int:
    if ctx.cmd == "reject" and not ctx.arg:
        ctx.fail("usage", 'usage: lume reject "<reason>"  (a reason is required)')
        return 2
    ws = ctx.require_ws()
    iteration = ws.transition(ctx.cmd, note=ctx.arg or None)  # GateError -> exit 1
    ctx.ok({"result": ctx.cmd, "workstream": ws.name, "iteration": iteration.id,
            "phase": iteration.phase},
           f"{ctx.cmd}: iteration {iteration.id:03d} -> phase {iteration.phase}")
    return 0
