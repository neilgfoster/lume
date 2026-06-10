"""Seed mode detection and mode-specific discovery DoD skeletons."""
from __future__ import annotations

from pathlib import Path

_SKELETON_NEW = (
    "- [ ] Why: the motivation for this project is captured.\n"
    "- [ ] Scope: what the project will and won't do is defined.\n"
    "- [ ] Constraints: key constraints (time, tech, team) are named.\n"
    "- [ ] Done-when: the objective's done-when clause is written and agreed."
)

_SKELETON_EXISTING = (
    "- [ ] Languages: the primary languages and runtimes are identified.\n"
    "- [ ] Layout: the repo structure (key dirs, entry points) is mapped.\n"
    "- [ ] Seams: the major extension points and interfaces are named.\n"
    "- [ ] Open questions: the most important unknowns are listed."
)


def detect_mode(project_root: Path) -> str:
    """Return 'existing' if the project root has files/dirs outside .lume/, else 'new'."""
    for p in project_root.iterdir():
        if p.name != ".lume":
            return "existing"
    return "new"


def skeleton_for_mode(mode: str) -> str:
    return _SKELETON_NEW if mode == "new" else _SKELETON_EXISTING
