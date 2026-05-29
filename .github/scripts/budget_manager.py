#!/usr/bin/env python3
"""
budget_manager.py — review panel budget tracking and deferral queue.

Tracks agent invocations per session window. Computes the current budget
tier to guide adversarial review dispatch decisions.

Usage:
  python3 .github/scripts/budget_manager.py              # full status
  python3 .github/scripts/budget_manager.py tier         # print tier only (for scripting)
  python3 .github/scripts/budget_manager.py record N     # record N invocations used
  python3 .github/scripts/budget_manager.py reset        # reset session counter (run when limit renews)
  python3 .github/scripts/budget_manager.py defer \\
      --pr 3 --branch chore/example --agents a,b,c \\
      --reason "REDUCED mode"                            # add agents to deferral queue
  python3 .github/scripts/budget_manager.py queue        # show deferral queue
  python3 .github/scripts/budget_manager.py drain N      # remove first N items from queue

Budget tiers (based on invocations used this session):
  FULL      — full panel, all agents at assigned model
  REDUCED   — mandatory agents only; optional agents deferred to queue
  MINIMAL   — scope-auditor only; all others deferred
  DEFERRED  — no live reviews; everything queued for next session

The session budget and tier thresholds live in .work/budget.json under "config"
and can be edited without touching this script.
"""

import argparse
import contextlib
import fcntl
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

try:
    import subprocess

    REPO_ROOT = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
except (subprocess.CalledProcessError, FileNotFoundError):
    REPO_ROOT = Path.cwd()

BUDGET_FILE = REPO_ROOT / ".work" / "budget.json"
QUEUE_FILE = REPO_ROOT / ".work" / "reviews" / "queue.json"

# PROVISIONAL defaults. These numbers are estimates, not measurements. They are
# intentionally exposed as config so they can be edited without changing this
# script. Replace with measured values once enough sessions of real burn data
# exist in the `history` array.
DEFAULT_CONFIG = {
    # Total agent invocations allowed per ~5h Pro plan window.
    "session_budget": 30,
    # Switch to REDUCED when this many invocations have been used.
    "reduced_at": 12,
    # Switch to MINIMAL when this many used.
    "minimal_at": 22,
    # Switch to DEFERRED when this many used.
    "deferred_at": 28,
}


# ---------------------------------------------------------------------------
# State I/O — concurrency- and crash-safe
#
# Concurrency- and crash-safety hardening:
# - fcntl.flock on a sidecar `.lock` for the read-modify-write window
# - atomic writes via tempfile + os.replace so SIGKILL during write never
#   leaves a truncated JSON
# - distinguish CORRUPT (rename to .corrupt-<ts> + warn) from MISSING
#   (return defaults) — silent default-reset destroyed history
# ---------------------------------------------------------------------------


def _default_budget() -> dict[str, Any]:
    return {
        "session": {
            "started": datetime.now(timezone.utc).isoformat(),
            "invocations_used": 0,
        },
        "config": DEFAULT_CONFIG.copy(),
        "coverage": {
            "recent": [],   # last N panels: [{pr, agents}]
            "cycle": 3,     # how many PRs before an optional agent is eligible again
        },
        "history": [],
    }


def _quarantine_corrupt(path: Path, exc: Exception) -> None:
    """Move a corrupt JSON file aside so the next save doesn't compound the loss."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    # Append (don't replace) the suffix so `.work/budget.json` becomes
    # `.work/budget.json.corrupt-<ts>`. Matches the .gitignore pattern.
    backup = path.with_name(f"{path.name}.corrupt-{ts}")
    try:
        path.rename(backup)
        print(
            f"WARN: {path} was unparseable ({type(exc).__name__}: {exc}); "
            f"moved aside to {backup}. Resetting to defaults.",
            file=sys.stderr,
        )
    except OSError as e:
        print(f"WARN: could not quarantine {path}: {e}", file=sys.stderr)


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via tempfile+os.replace so a crash never truncates."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; never leave a hanging .tmp file.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _read_or_default(path: Path, default_factory: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        return default_factory()
    try:
        with open(path) as f:
            return cast(dict[str, Any], json.load(f))
    except (json.JSONDecodeError, OSError) as exc:
        _quarantine_corrupt(path, exc)
        return default_factory()


@contextlib.contextmanager
def _locked(path: Path) -> Generator[None, None, None]:
    """Hold an exclusive flock on a sidecar lock file for the lifetime of the
    `with` block. Read-modify-write callers must wrap the entire sequence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _load_budget() -> dict[str, Any]:
    return _read_or_default(BUDGET_FILE, _default_budget)


def _save_budget(data: dict[str, Any]) -> None:
    _atomic_write(BUDGET_FILE, data)


def _load_queue() -> dict[str, Any]:
    return _read_or_default(QUEUE_FILE, lambda: {"queue": []})


def _save_queue(data: dict[str, Any]) -> None:
    _atomic_write(QUEUE_FILE, data)


# ---------------------------------------------------------------------------
# Tier logic
# ---------------------------------------------------------------------------


def get_tier(budget: dict[str, Any] | None = None) -> str:
    if budget is None:
        budget = _load_budget()
    used = budget["session"]["invocations_used"]
    cfg = budget["config"]
    if used >= cfg["deferred_at"]:
        return "DEFERRED"
    if used >= cfg["minimal_at"]:
        return "MINIMAL"
    if used >= cfg["reduced_at"]:
        return "REDUCED"
    return "FULL"


def tier_description(tier: str) -> str:
    return {
        "FULL": "all agents run at assigned model",
        "REDUCED": "mandatory agents only — optionals deferred to queue",
        "MINIMAL": "scope-auditor only — all others deferred",
        "DEFERRED": "no live reviews — everything queued for next session",
    }[tier]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_status(budget: dict[str, Any], queue: dict[str, Any]) -> None:
    tier = get_tier(budget)
    used = budget["session"]["invocations_used"]
    cap = budget["config"]["session_budget"]
    remaining = cap - used
    pending = len(queue["queue"])

    print(f"Budget tier : {tier} — {tier_description(tier)}")
    print(f"Invocations : {used}/{cap} used  ({remaining} remaining)")
    print(f"Deferred    : {pending} item(s) in queue")

    if pending:
        print("\nDeferred queue:")
        for i, item in enumerate(queue["queue"][:5], 1):
            agents = ", ".join(item.get("agents", []))
            print(f"  [{i}] PR #{item.get('pr', '?')} — {agents}")
        if pending > 5:
            print(f"  ... and {pending - 5} more (run `budget_manager.py queue` to see all)")

    cfg = budget["config"]
    print(
        f"\nThresholds  : REDUCED at {cfg['reduced_at']}, "
        f"MINIMAL at {cfg['minimal_at']}, "
        f"DEFERRED at {cfg['deferred_at']}"
    )
    print("To reset    : python3 .github/scripts/budget_manager.py reset")


def cmd_tier() -> None:
    print(get_tier())


def cmd_record(n: int) -> None:
    with _locked(BUDGET_FILE):
        budget = _load_budget()
        budget["session"]["invocations_used"] += n
        _save_budget(budget)
        # Capture reporting values inside the lock so they are consistent
        # with what was written — reading budget after the lock releases
        # would use a stale local copy.
        tier = get_tier(budget)
        used = budget["session"]["invocations_used"]
        cap = budget["config"]["session_budget"]
    print(f"Recorded {n} invocation(s). Used: {used}/{cap}. Tier: {tier}")


def cmd_reset() -> None:
    with _locked(BUDGET_FILE):
        budget = _load_budget()
        old = budget["session"]["invocations_used"]
        # Archive current session before reset
        budget["history"].append({
            "ended": datetime.now(timezone.utc).isoformat(),
            "started": budget["session"].get("started"),
            "invocations_used": old,
        })
        # Keep last 10 history entries
        budget["history"] = budget["history"][-10:]
        budget["session"] = {
            "started": datetime.now(timezone.utc).isoformat(),
            "invocations_used": 0,
        }
        _save_budget(budget)
    print(f"Session reset. Previous: {old} invocations used.")


_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.\-]{0,99}$")


_AGENT_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")
_PRINTABLE_RE = re.compile(r"^[ -~]{1,200}$")  # printable ASCII, max 200 chars


def cmd_defer(pr: int, branch: str, agents: list[str], reason: str) -> None:
    if not agents:
        print("No agents to defer.", file=sys.stderr)
        sys.exit(1)
    if not _BRANCH_RE.match(branch):
        print(f"error: branch name '{branch}' contains invalid characters", file=sys.stderr)
        sys.exit(1)
    invalid_agents = [a for a in agents if not _AGENT_RE.match(a)]
    if invalid_agents:
        print(f"error: invalid agent name(s): {', '.join(invalid_agents)}", file=sys.stderr)
        sys.exit(1)
    if not _PRINTABLE_RE.match(reason):
        print("error: --reason must be 1-200 printable ASCII characters", file=sys.stderr)
        sys.exit(1)
    with _locked(QUEUE_FILE):
        queue = _load_queue()
        # Use a timestamp-based ID so drain/defer cycles don't collide.
        # len(queue)+1 resets to a previously-used value after drain.
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        entry = {
            "id": f"deferred-{ts}",
            "pr": pr,
            "branch": branch,
            "deferred_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "agents": agents,
        }
        queue["queue"].append(entry)
        _save_queue(queue)
    print(f"Deferred {len(agents)} agent(s) as {entry['id']} (PR #{pr})")


def cmd_queue(queue: dict[str, Any]) -> None:
    items = queue["queue"]
    if not items:
        print("Deferral queue is empty.")
        return
    print(f"{len(items)} item(s) in queue:\n")
    for item in items:
        agents = ", ".join(item.get("agents", []))
        print(f"  {item['id']}  PR #{item.get('pr', '?')} ({item.get('branch', '?')})")
        print(f"    deferred : {item.get('deferred_at', '?')}")
        print(f"    reason   : {item.get('reason', '?')}")
        print(f"    agents   : {agents}")
        print()


def cmd_drain(n: int, _queue_unused: dict[str, Any]) -> None:
    # Read-modify-write under lock; the caller-provided queue snapshot can
    # be stale if another writer raced us, so we re-read inside the lock.
    with _locked(QUEUE_FILE):
        queue = _load_queue()
        if not queue["queue"]:
            print("Queue is already empty.")
            return
        removed = queue["queue"][:n]
        queue["queue"] = queue["queue"][n:]
        _save_queue(queue)
    ids = ", ".join(item["id"] for item in removed)
    print(f"Drained {len(removed)} item(s): {ids}")
    print(f"Remaining in queue: {len(queue['queue'])}")


def cmd_record_panel(pr: int, agents: list[str]) -> None:
    """Record which agents ran on a PR for rotation tracking."""
    with _locked(BUDGET_FILE):
        budget = _load_budget()
        recent = budget["coverage"]["recent"]
        recent.append({"pr": pr, "agents": agents})
        cycle = budget["coverage"]["cycle"]
        budget["coverage"]["recent"] = recent[-cycle:]
        _save_budget(budget)
    print(f"Recorded panel for PR #{pr}: {', '.join(agents)}")


def cmd_suggest_rotation(all_optional: list[str]) -> None:
    """Print optional agents not run recently — candidates for next panel."""
    budget = _load_budget()
    recent = budget["coverage"]["recent"]
    cycle = budget["coverage"]["cycle"]
    recently_used: set[str] = set()
    for entry in recent[-cycle:]:
        recently_used.update(entry.get("agents", []))
    candidates = [a for a in all_optional if a not in recently_used]
    if not candidates:
        candidates = all_optional  # all recently used — reset rotation
    print("\n".join(candidates))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


CLI_SPEC: dict[str, Any] = {
    "name": "budget_manager",
    "script": "budget_manager.py",
    "description": "Review panel budget tracking and deferral queue.",
    "invocation": "python3 .github/scripts/budget_manager.py",
    "commands": [
        {
            "name": "(default)",
            "description": "Show full budget status including tier, usage, and queue depth",
            "args": [],
            "output": "Prints tier, invocations used/cap, queue depth, and thresholds.",
        },
        {
            "name": "tier",
            "description": "Print current budget tier name only",
            "args": [],
            "output": "Prints one of: FULL, REDUCED, MINIMAL, DEFERRED.",
        },
        {
            "name": "record",
            "description": "Record N agent invocations used",
            "args": [
                {
                    "flag": "n",
                    "type": "int",
                    "required": True,
                    "help": "Number of invocations to record",
                },
            ],
            "output": "Exits 0. Prints updated usage and current tier.",
        },
        {
            "name": "reset",
            "description": "Reset session invocation counter, archive current session",
            "args": [],
            "output": "Exits 0. Archives current session, resets counter to 0.",
        },
        {
            "name": "defer",
            "description": "Add agents to the deferral queue for a PR",
            "args": [
                {"flag": "--pr",     "type": "int", "required": True,  "help": "PR number"},
                {"flag": "--branch", "type": "str", "required": True,  "help": "Branch name"},
                {"flag": "--agents", "type": "str", "required": True,  "help": "Comma-separated agent names"},
                {"flag": "--reason", "type": "str", "required": False, "help": "Reason for deferral (default: budget constraint)"},
            ],
            "output": "Exits 0. Prints deferred entry ID.",
        },
        {
            "name": "queue",
            "description": "Show all items in the deferral queue",
            "args": [],
            "output": "Prints each queued item with PR, branch, agents, and reason.",
        },
        {
            "name": "drain",
            "description": "Remove first N items from the deferral queue",
            "args": [
                {
                    "flag": "n",
                    "type": "int",
                    "required": False,
                    "help": "Number of items to remove (default: 1)",
                },
            ],
            "output": "Exits 0. Prints removed item IDs and remaining count.",
        },
        {
            "name": "record-panel",
            "description": "Record which agents ran on a PR for rotation tracking",
            "args": [
                {"flag": "--pr",     "type": "int", "required": True, "help": "PR number"},
                {"flag": "--agents", "type": "str", "required": True, "help": "Comma-separated agent names"},
            ],
            "output": "Exits 0. Prints confirmation.",
        },
        {
            "name": "suggest-rotation",
            "description": "List optional agents not run recently - candidates for next panel",
            "args": [
                {
                    "flag": "--optional",
                    "type": "str",
                    "required": True,
                    "help": "Comma-separated full optional agent list",
                },
            ],
            "output": "Prints one agent name per line.",
        },
    ],
}


def main() -> int:
    if "--schema" in sys.argv:
        print(json.dumps(CLI_SPEC, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Review panel budget and deferral queue")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("tier", help="Print current tier name only")
    sub.add_parser("reset", help="Reset session invocation counter")
    sub.add_parser("queue", help="Show deferral queue")

    p_record = sub.add_parser("record", help="Record N invocations used")
    p_record.add_argument("n", type=int, help="Number of invocations to record")

    p_panel = sub.add_parser("record-panel", help="Record which agents ran for rotation tracking")
    p_panel.add_argument("--pr", type=int, required=True)
    p_panel.add_argument("--agents", required=True, help="Comma-separated agent names")

    p_defer = sub.add_parser("defer", help="Add agents to deferral queue")
    p_defer.add_argument("--pr", type=int, required=True)
    p_defer.add_argument("--branch", required=True)
    p_defer.add_argument("--agents", required=True, help="Comma-separated agent names")
    p_defer.add_argument("--reason", default="budget constraint")

    p_drain = sub.add_parser("drain", help="Mark first N queue items as processed")
    p_drain.add_argument("n", type=int, nargs="?", default=1)

    p_rotate = sub.add_parser("suggest-rotation", help="List optional agents due for rotation")
    p_rotate.add_argument("--optional", required=True, help="Comma-separated full optional agent list")

    args = parser.parse_args()

    budget = _load_budget()
    queue = _load_queue()

    if args.cmd is None:
        cmd_status(budget, queue)
    elif args.cmd == "tier":
        cmd_tier()
    elif args.cmd == "record":
        cmd_record(args.n)
    elif args.cmd == "reset":
        cmd_reset()
    elif args.cmd == "defer":
        agents = [a.strip() for a in args.agents.split(",") if a.strip()]
        cmd_defer(args.pr, args.branch, agents, args.reason)
    elif args.cmd == "queue":
        cmd_queue(queue)
    elif args.cmd == "drain":
        cmd_drain(args.n, queue)
    elif args.cmd == "record-panel":
        agents = [a.strip() for a in args.agents.split(",") if a.strip()]
        cmd_record_panel(args.pr, agents)
    elif args.cmd == "suggest-rotation":
        optional = [a.strip() for a in args.optional.split(",") if a.strip()]
        cmd_suggest_rotation(optional)

    return 0


if __name__ == "__main__":
    sys.exit(main())
