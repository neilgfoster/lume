"""Adopters + the git reach that reads their capability gaps.

ADOPTERS.json (repo root) is the deterministic source of truth for who uses lume
(ADOPTERS.md's table is generated from it). `read_adopters` returns those rows;
`reach_gaps` reads one adopter repo's gaps/ by git clone/fetch + an ephemeral
worktree, caching the clone under .lume/cache/adopters/.

Reading is data-only (JSON), but cloning an adopter repo does fetch its content
to disk - callers should treat adopter repos with the trust that implies. A git
failure raises LumeError; the per-adopter skip-and-continue policy lives in the
scan that calls this (P17).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import gap
from .errors import LumeError
from .validate import validate_entity


def read_adopters(repo_root) -> list[dict]:
    """The adopter rows from repo_root/ADOPTERS.json (validated)."""
    doc = json.loads((Path(repo_root) / "ADOPTERS.json").read_text())
    validate_entity("adopters", doc)
    return doc["adopters"]


def adopter_cache_root(repo_root) -> Path:
    """Where cached adopter clones live (gitignored)."""
    return Path(repo_root) / ".lume" / "cache" / "adopters"


def _git(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        capture_output=True, text=True)
    if proc.returncode != 0:
        where = f" (cwd={cwd})" if cwd else ""
        raise LumeError(f"git {' '.join(args)} failed{where}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _default_ref(clone_dir: Path) -> str:
    """The remote's default branch as 'origin/<branch>', best-effort."""
    try:
        head = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=clone_dir)
        if head:
            return head
    except LumeError:
        pass
    return "HEAD"


def reach_gaps(url: str, slug: str, cache_root, ref: str | None = None) -> list[dict]:
    """Clone/fetch the adopter repo and read its gaps/ via an ephemeral worktree.

    Caches the clone under cache_root/<slug>/. Adds a detached worktree at the
    default ref (or `ref`), reads gaps, and ALWAYS removes the worktree. Raises
    LumeError on any git failure.
    """
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    clone_dir = cache_root / slug
    if (clone_dir / ".git").is_dir():
        _git(["fetch", "--prune", "origin"], cwd=clone_dir)
    else:
        _git(["clone", url, str(clone_dir)])
    target = ref or _default_ref(clone_dir)
    worktree = cache_root / f"{slug}.wt"
    _git(["worktree", "add", "--detach", "--force", str(worktree), target], cwd=clone_dir)
    try:
        return gap.read_gaps(worktree)
    finally:
        _git(["worktree", "remove", "--force", str(worktree)], cwd=clone_dir)
