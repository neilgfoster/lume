"""Migrate existing markdown workstreams into validated state.json (P3).

A one-shot, idempotent converter. It reuses the engine's own parsers - objective
frontmatter (status), Iteration (frontmatter + title), parse_plan - so there is
one parsing definition, not two. Verdict outcomes, the one piece of state today
encoded as prose, are extracted with a STRICT stamp regex so prose that merely
mentions ACCEPTED/REJECTED is never miscounted. Built docs are written via
Repository.save_state, which validates, so a malformed migration fails loudly.

Markdown artifacts are left in place; P4 rewires the mutating verbs onto the
JSON this produces.
"""
from __future__ import annotations

from pathlib import Path

from .iteration import Iteration, parse_verdicts  # noqa: F401  (re-exported for callers)
from .plan import PlanItem
from .repository import Repository
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
    return {
        "id": item.id,
        "type": item.type,
        "iter": item.iter_id,
        "tag": item.tag,
        "sketch": item.sketch,
    }


def build_doc(ws: Workstream) -> dict:
    """Build a state document from a workstream's existing markdown."""
    return {
        "workstream": {
            "slug": ws.name,
            "title": ws.objective_line(),
            "status": ws.status,
            "objective_artifact": "objective.md",
        },
        "iterations": [_iteration_entity(it) for it in ws.iterations()],
        "plan": [_plan_entity(p) for p in (ws.plan_items() or [])],
    }


def migrate_all(repo: Repository, lume_dir: Path) -> list[str]:
    """Migrate every workstream under `lume_dir` to state.json. Returns slugs written."""
    written = []
    for ws in repo.workstreams(lume_dir):
        repo.save_state(ws.name, build_doc(ws))
        written.append(ws.name)
    return written
