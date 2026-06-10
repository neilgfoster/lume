"""Migrate existing markdown workstreams into validated state.json (P3),
objective.json (P10), and iterations/NNN.json (P11).

A one-shot, idempotent converter. Reuses the engine's own parsers so there is
one parsing definition, not two. Built docs are written via Repository.save_state,
which validates, so a malformed migration fails loudly.

Markdown artifacts are left in place or regenerated as views. After P5, verbs
read from state.json; after P10 from objective.json; after P11 from NNN.json.
Migrate is the explicit legacy-to-JSON bridge.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import frontmatter
from . import state as state_mod
from .iteration import Iteration, parse_verdicts  # noqa: F401  (re-exported for callers)
from .repository import Repository
from .plan import PlanItem, parse_plan
from .workstream import Workstream

# Legacy iteration types -> their current vocabulary equivalent. `build` was the
# original hardcoded type, retired by the lifecycle workstream in favour of
# `execution` (its 005 note: "006 onward default to execution"). `review` was
# build-lume's pre-closeout retro type (its 006 is "Retro ... and close
# build-lume") -> `closeout`. Normalising on migration is faithful to those
# documented supersessions.
_LEGACY_TYPES = {"build": "execution", "review": "closeout"}


def _iteration_entity(it: Iteration) -> dict:
    # The entity shape comes from the model; migration only normalises the
    # legacy type vocabulary on top of it.
    entity = it.to_entity()
    entity["type"] = _LEGACY_TYPES.get(it.type, it.type)
    return entity


def _plan_entity(item: PlanItem) -> dict:
    return item.to_entity()


def build_doc_from_markdown(ws_dir: Path) -> dict:
    """Build a state document by reading markdown directly from ws_dir.

    Does not use a Workstream object, so no state.json is required on entry.
    This is the explicit migration path; the verbs (via Workstream) use state.json.
    """
    obj_text = (ws_dir / "objective.md").read_text()
    obj_meta, obj_body = frontmatter.parse(obj_text)
    status = obj_meta.get("status", "active")
    title = ""
    for line in obj_body.splitlines():
        stripped = line.lstrip("# ").strip()
        if stripped:
            title = stripped
            break

    iter_dir = ws_dir / "iterations"
    iterations = []
    if iter_dir.is_dir():
        for p in sorted(p for p in iter_dir.glob("*.md") if p.stem.isdigit()):
            it = Iteration.from_text(p.read_text())
            iterations.append(_iteration_entity(it))

    plan_items = []
    plan_path = ws_dir / "plan.md"
    if plan_path.is_file():
        plan_items = [_plan_entity(p) for p in parse_plan(plan_path.read_text())]

    return {
        "workstream": {
            "slug": ws_dir.name,
            "title": title,
            "status": status,
            "objective_artifact": "objective.json",
        },
        "iterations": iterations,
        "plan": plan_items,
    }


def _objective_prose(ws_dir: Path) -> str:
    """Extract the prose body from objective.md (everything after the title heading)."""
    obj_text = (ws_dir / "objective.md").read_text()
    _, body = frontmatter.parse(obj_text)
    lines = body.splitlines()
    # Skip the leading heading line (# Title).
    for i, line in enumerate(lines):
        if line.startswith("#"):
            rest = lines[i + 1:]
            # Strip leading blank lines.
            while rest and not rest[0].strip():
                rest = rest[1:]
            return "\n".join(rest).strip()
    return body.strip()


def _extract_section(body: str, heading: str) -> str:
    """Extract content between `## heading` and the next `##` heading."""
    lines = body.splitlines()
    in_sec = False
    result: list[str] = []
    pattern = re.compile(r"^##\s+" + re.escape(heading) + r"\s*$", re.IGNORECASE)
    for line in lines:
        if pattern.match(line):
            in_sec = True
            continue
        if in_sec:
            if re.match(r"^##\s+", line):
                break
            result.append(line)
    return "\n".join(result).strip()


_ITEM_RE = re.compile(r"^-\s+\[([ x])\]\s+(.*)")
_PLACEHOLDER = frozenset({"(filled at hand-back)", "(operator: accept / reject + reasons)"})


def _parse_iter_content(body: str, iter_id: int) -> dict:
    """Parse iteration body markdown into an iteration_content doc."""
    dod_raw = _extract_section(body, "DoD")
    sr_raw = _extract_section(body, "Self-review")
    hb_raw = _extract_section(body, "Handback")

    # Split DoD into preamble lines and checklist items (multi-line item aware).
    preamble_lines: list[str] = []
    items: list[dict] = []
    current: dict | None = None

    for line in (dod_raw or "").splitlines():
        m = _ITEM_RE.match(line)
        if m:
            if current is not None:
                items.append(current)
            current = {"checked": m.group(1) == "x", "_parts": [m.group(2)]}
        elif current is not None:
            stripped = line.strip()
            if stripped:
                current["_parts"].append(stripped)
        else:
            preamble_lines.append(line)
    if current is not None:
        items.append(current)

    item_entities = [
        {"text": "\n".join(i["_parts"]).strip(), "checked": i["checked"]}
        for i in items
    ]

    def clean(s: str) -> str | None:
        s = s.strip()
        return s if s and s not in _PLACEHOLDER else None

    return {
        "id": iter_id,
        "dod": {"preamble": "\n".join(preamble_lines).strip(), "items": item_entities},
        "self_review": clean(sr_raw),
        "handback": clean(hb_raw),
    }


def migrate_iterations(ws_dir: Path, doc: dict) -> None:
    """Create iterations/NNN.json for each iteration; update dod_artifact in doc.

    Idempotent: skips NNN.json creation if already exists. Always ensures
    dod_artifact in state.json points to the .json file, re-saving if changed.
    """
    from .clock import SystemClock

    iter_dir = ws_dir / "iterations"
    changed = False
    ws = Workstream(ws_dir, SystemClock(), doc)

    for entity in doc["iterations"]:
        n = entity["id"]
        target = f"iterations/{n:03d}.json"
        if entity.get("dod_artifact") != target:
            entity["dod_artifact"] = target
            changed = True

        json_path = iter_dir / f"{n:03d}.json"
        if json_path.is_file():
            continue

        md_path = iter_dir / f"{n:03d}.md"
        if md_path.is_file():
            _, body = frontmatter.parse(md_path.read_text())
            content = _parse_iter_content(body, n)
        else:
            content = {"id": n, "dod": {"preamble": "", "items": []},
                       "self_review": None, "handback": None}

        ws._save_iter_content(n, content)
        changed = True

    if changed:
        state_mod.save(ws_dir / state_mod.STATE_FILE, doc)


def migrate_objective(ws_dir: Path, doc: dict) -> None:
    """Write objective.json for ws_dir (JSON-only).

    Idempotent: skips if objective.json already exists with matching status.
    Uses the prose from the existing objective.md as the `text` field.
    """
    obj_path = ws_dir / "objective.json"
    ws_meta = doc["workstream"]

    # Idempotency: if objective.json already exists and status matches, skip.
    if obj_path.is_file():
        import json
        existing = json.loads(obj_path.read_text())
        if existing.get("status") == ws_meta["status"]:
            return

    text = _objective_prose(ws_dir) if (ws_dir / "objective.md").is_file() else ""
    obj_doc = {
        "slug": ws_meta["slug"],
        "title": ws_meta["title"],
        "status": ws_meta["status"],
        "text": text,
    }
    # Use Workstream helpers for validation (no clock needed here).
    from .clock import SystemClock
    ws = Workstream(ws_dir, SystemClock(), doc)
    ws._save_objective(obj_doc)


def migrate_decisions(ws_dir: Path, doc: dict) -> None:
    """Parse decisions.md into decisions.json (JSON-only).

    No-op when there is no decisions.md.
    """
    from .clock import SystemClock
    from .decisions import parse_decisions_md

    md_path = ws_dir / "decisions.md"
    if not md_path.is_file():
        return
    entries = parse_decisions_md(md_path.read_text())
    ws = Workstream(ws_dir, SystemClock(), doc)
    ws._save_decisions({"entries": entries})


def migrate_retro(ws_dir: Path, doc: dict) -> None:
    """Parse retro.md into retro.json (best-effort, JSON-only).

    No-op when there is no retro.md.
    """
    from .clock import SystemClock
    from .retro import parse_retro_md

    md_path = ws_dir / "retro.md"
    if not md_path.is_file():
        return
    retro = parse_retro_md(md_path.read_text())
    ws = Workstream(ws_dir, SystemClock(), doc)
    ws.save_retro(retro)


def migrate_discovery(ws_dir: Path, doc: dict) -> None:
    """Parse discovery.md into discovery.json (JSON-only).

    No-op when there is no discovery.md.
    """
    import json as _json
    from .discovery import parse_discovery_md
    from .validate import validate_entity

    md_path = ws_dir / "discovery.md"
    if not md_path.is_file():
        return
    disc = parse_discovery_md(md_path.read_text())
    validate_entity("discovery", disc)
    (ws_dir / "discovery.json").write_text(
        _json.dumps(disc, indent=2, sort_keys=True) + "\n"
    )


def migrate_all(repo: Repository, lume_dir: Path) -> list[str]:
    """Migrate every workstream under `lume_dir` to state.json + objective.json.

    Iterates workstream directories directly. Works on first migration (no
    state.json required). Idempotent.
    """
    written = []
    ws_root = lume_dir / "workstreams"
    if not ws_root.is_dir():
        return written
    for ws_dir in sorted(
        p for p in ws_root.iterdir()
        if (p / "objective.md").is_file() or (p / "state.json").is_file()
    ):
        if (ws_dir / "objective.md").is_file():
            # Legacy markdown source: build state.json + JSON artifacts from it.
            doc = build_doc_from_markdown(ws_dir)
            repo.save_state(ws_dir.name, doc)
            migrate_objective(ws_dir, doc)
            migrate_iterations(ws_dir, doc)
        elif (ws_dir / state_mod.STATE_FILE).is_file():
            # Already flipped to JSON: state.json is the source; only any
            # remaining authored .md (discovery) still needs converting.
            doc = repo.load_state(ws_dir.name)
        else:
            continue
        migrate_decisions(ws_dir, doc)
        migrate_retro(ws_dir, doc)
        migrate_discovery(ws_dir, doc)
        written.append(ws_dir.name)
    return written
