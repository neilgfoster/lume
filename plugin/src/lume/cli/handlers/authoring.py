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


def handle_gap(ctx: Context) -> int:
    """Capture/list cross-repo capability gaps (repo-level, not -w scoped).

    `lume gap add "<title>" [-c <context>]` records a gap in the current repo;
    `lume gap list` prints them; `lume gap scan` ingests adopters' open gaps;
    `lume gap link <source> <id> -w <ws>` records the workstream answering a
    gap; `lume gap resolve <source> <id> [-w <ws>] [-t <kind>] ["<note>"]`
    resolves one with a structured resolution.
    """
    from ...adopters import scan_and_ingest
    from ...gap import add_gap, link_gap, read_gaps, resolve_gap

    sub = ctx.arg
    if sub not in ("add", "list", "scan", "link", "resolve"):
        ctx.fail("usage", "usage: lume gap <add|list|scan|link|resolve> ...")
        return 2
    root = ctx.repo.project_root()  # NoLumeDirError -> dispatch maps to exit 1

    if sub == "scan":
        report = scan_and_ingest(root)  # LumeError -> dispatch maps to exit 1
        if ctx.json_mode:
            ctx.out(report)
            return 0
        print(f"gap scan: {len(report['ingested'])} ingested, "
              f"{len(report['already_present'])} already present, "
              f"{len(report['failed'])} adopter(s) failed")
        for f in report["failed"]:
            print(f"  ! {f['adopter']}: {f['error']}")
        return 0

    if sub == "link":
        source = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
        gap_id = ctx.rest[4].strip() if len(ctx.rest) > 4 else ""
        if not source or not gap_id or ctx.target is None:
            ctx.fail("usage", "usage: lume gap link <source> <id> -w <workstream>")
            return 2
        ws = ctx.require_ws()  # unknown workstream -> LumeError -> exit 1
        rec = link_gap(root, source, gap_id, ws.id)  # LumeError -> exit 1
        ctx.ok({"result": "gap_link", "source": rec["source"], "id": rec["id"],
                "workstreams": rec["workstreams"]},
               f"gap link: {rec['source']}/{rec['id']} <- workstream {ws.id}")
        return 0

    if sub == "resolve":
        source = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
        gap_id = ctx.rest[4].strip() if len(ctx.rest) > 4 else ""
        note = ctx.rest[5].strip() if len(ctx.rest) > 5 else ""
        if not source or not gap_id:
            ctx.fail("usage",
                     'usage: lume gap resolve <source> <id> [-w <ws>] [-t <kind>] ["<note>"]')
            return 2
        kind = ctx.opt_type or "implemented"
        if kind not in ("implemented", "wont-fix", "superseded", "duplicate"):
            ctx.fail("usage", "kind must be implemented, wont-fix, superseded "
                              f"or duplicate, got '{kind}'.")
            return 2
        ws_id = ctx.require_ws().id if ctx.target is not None else None
        rec = resolve_gap(root, source, gap_id, kind=kind, note=note,
                          workstream_id=ws_id)  # LumeError -> exit 1
        ctx.ok({"result": "gap_resolve", "source": rec["source"], "id": rec["id"],
                "status": rec["status"], "resolution": rec["resolution"]},
               f"gap resolve: {rec['source']}/{rec['id']} -> {rec['status']} "
               f"({rec['resolution']['kind']})")
        return 0

    if sub == "add":
        title = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
        if not title:
            ctx.fail("usage", 'usage: lume gap add "<title>" [-c <context>]')
            return 2
        record = add_gap(root, title=title, source=root.name,
                         created=ctx.repo.today(), context=ctx.opt_context or "")
        ctx.ok({"result": "gap_add", "id": record["id"], "source": record["source"],
                "status": record["status"], "title": record["title"]},
               f"gap add: {record['id']} ({record['source']}, {record['status']}): {record['title']}")
        return 0

    # sub == "list"
    records = read_gaps(root)
    if ctx.json_mode:
        ctx.out(records)
        return 0
    if not records:
        print("(no gaps)")
        return 0
    for r in records:
        print(f"{r['id']}  {r['status']:12}  {r['source']}  {r['title']}")
    return 0


def handle_review_ingest(ctx: Context) -> int:
    """Ingest a review result: validate, capture, and emit the queue plan.

    Writes findings.md into the dated .lume/reviews/<date>-NN/ folder (the one
    sanctioned raw file write) and persists the structured result through the
    store seam. The queue-command plan is PRINTED, never executed - creating
    workstreams, decisions, and gaps stays behind the operator's gate.
    """
    import json
    from pathlib import Path

    from ...errors import SchemaError
    from ...review import (build_findings_md, next_review_slug, queue_commands,
                           result_to_store_doc)
    from ...validate import validate_entity

    path_arg = ctx.rest[3].strip() if len(ctx.rest) > 3 else ""
    if not path_arg:
        ctx.fail("usage", "usage: lume review ingest <path>")
        return 2
    path = Path(path_arg)
    if not path.is_file():
        ctx.fail("usage", f"no review-result file at '{path_arg}'.")
        return 2
    try:
        result = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        ctx.fail("usage", f"'{path_arg}' is not valid JSON: {exc}.")
        return 2
    try:
        validate_entity("review_result", result)
    except SchemaError as exc:
        ctx.fail("usage", f"invalid review result: {exc}")
        return 2

    root = ctx.repo.project_root()  # NoLumeDirError -> dispatch maps to exit 1
    lume_dir = root / ".lume"
    slug = next_review_slug(lume_dir, ctx.repo.today())

    findings = build_findings_md(result, slug)
    folder = lume_dir / "reviews" / slug
    folder.mkdir(parents=True, exist_ok=False)  # slug is the next free one
    (folder / "findings.md").write_text(findings + "\n")
    ctx.repo.save_review(slug, result_to_store_doc(result, slug))

    commands = queue_commands(result, slug)
    if ctx.json_mode:
        ctx.out({"result": "review_ingest", "review": slug,
                 "findings": f".lume/reviews/{slug}/findings.md",
                 "queue_plan": commands})
        return 0
    print(f"review ingest: captured {path_arg} -> .lume/reviews/{slug}/findings.md")
    print("queue plan (run these to adopt the results - lume did NOT run them):")
    for cmd in commands:
        print(f"  {cmd}")
    if not commands:
        print("  (nothing to queue)")
    return 0
