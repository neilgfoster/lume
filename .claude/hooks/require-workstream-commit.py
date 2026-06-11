#!/usr/bin/env python3
"""Repo-local PreToolUse gate: no `git commit` outside a working lume iteration.

This enforces a way of working that is specific to the lume REPO (it is wired in
this repo's .claude/settings.json) and is deliberately NOT part of the lume
plugin shipped to users - nothing here lives under plugin/.

Policy (commit-only chokepoint): the agent may read, explore, and edit freely,
but a `git commit` is allowed only while an active lume workstream has a current
iteration in the `working` phase. Anything else that runs `git commit` is denied
with a reason. Every other tool call - and every non-commit Bash command - passes
through untouched.

It gates the AGENT (Claude's tool calls), not the operator's own editor/terminal
edits, which this hook never sees. It is a chokepoint, not a sandbox: raw file
writes are not blocked, but they cannot LAND without a gated `git commit`.

Contract: read the PreToolUse event JSON on stdin. To deny, print
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
"permissionDecision": "deny", "permissionDecisionReason": "..."}} and exit 0.
To allow / not decide, exit 0 with no output.
"""

import json
import os
import re
import sys
from pathlib import Path

# Matches a `git commit ...` invocation anywhere in a (possibly compound)
# command: start of string or a shell separator, then `git` and `commit` as
# whole words. Tolerant of flags, heredocs, and `&&`/`;`/`|` chaining. The
# `(?![\w-])` guard keeps sibling subcommands like `commit-graph`/`commit-tree`
# from matching the `commit` subcommand.
_GIT_COMMIT_RE = re.compile(
    r"(?:^|[\s;&|(])git\s+(?:-[^\s]+\s+)*commit(?![\w-])"
)


def _repo_root(event: dict) -> Path:
    """Locate the repo root: prefer CLAUDE_PROJECT_DIR, else the event cwd,
    else walk up from this script (.claude/hooks/ -> repo root)."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = event.get("cwd")
    if cwd:
        return Path(cwd)
    return Path(__file__).resolve().parents[2]


def _has_working_iteration(repo_root: Path) -> bool:
    """True iff some active workstream's latest iteration is in `working`."""
    for state_path in sorted((repo_root / ".lume" / "workstreams").glob("*/state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (state.get("workstream") or {}).get("status") != "active":
            continue
        iterations = state.get("iterations") or []
        if iterations and iterations[-1].get("phase") == "working":
            return True
    return False


def _deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # Can't parse the event - do not interfere.

    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command") or ""
    if not _GIT_COMMIT_RE.search(command):
        return 0  # Not a commit - pass through.

    if _has_working_iteration(_repo_root(event)):
        return 0  # Allowed: a workstream is actively working.

    _deny(
        "Repo policy (lume): every change to this repo must go through a lume "
        "workstream, so `git commit` is allowed only while an active workstream "
        "has a current iteration in the `working` phase. None is working now. "
        "Open/continue a workstream and reach `working` first: `lume status`, "
        "then `lume open ...` -> `lume approve` -> `lume start`, or `lume start` "
        "on the current iteration. (Driving the loop and editing .lume/ need no "
        "commit, so this never deadlocks.) This gate is repo-local and not part "
        "of the lume plugin."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
