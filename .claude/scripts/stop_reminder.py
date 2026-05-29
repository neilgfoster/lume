#!/usr/bin/env python3
"""Stop hook: remind the operator about open PRs and the deterministic gate.

Best-effort reminder. Failures are surfaced as one-line warnings rather than
swallowed.

Hardenings applied here:

- SEC3 — `gh pr list` invocation uses `--head=<branch>` and the branch
  name is validated against a strict regex before being passed to gh,
  so a branch beginning with `-` (which `git branch --show-current`
  cannot in practice produce, but defence-in-depth) cannot inject a
  flag.
- CE7 / EC12 / OP3 — if gh is missing, unauthenticated, or rate-limited,
  the script reports a distinct warning instead of silently skipping
  the reminder.
- read-only `gh pr list` calls only; the per-Stop cost is bounded by
  `_GH_TIMEOUT_SECONDS`.
- OP4 — newlines are emitted via `print` (Python), not bash `echo "\\n"`
  which printed literal `\n` on non-POSIX shells.
- FE5 — implemented in Python rather than inline bash for portability.

Always exits 0.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.\-]{0,99}$")
_GH_TIMEOUT_SECONDS = 5
_AM_I_DONE_REL = ".github/scripts/am_i_done.py"


def _print(msg: str) -> None:
    """Newline-prefixed so the message stands out in a busy transcript."""
    print(f"\n[hedl] {msg}")


def _current_branch(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    if not branch or branch == "HEAD":
        return None
    if not _BRANCH_RE.match(branch):
        # Conservative: refuse to pass an unusual branch name to gh.
        return None
    return branch


def _open_pr_for_branch(branch: str, repo_root: Path) -> tuple[int | None, str | None]:
    """Return (pr_number_or_None, error_message_or_None)."""
    if not shutil.which("gh"):
        return None, "gh CLI not on PATH; PR-open check skipped"

    try:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                f"--head={branch}",
                "--state", "open",
                "--json", "number",
                "--limit", "1",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, f"gh timed out after {_GH_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return None, f"could not run gh: {exc}"

    if result.returncode != 0:
        err_low = (result.stderr or "").lower()
        if "authentication" in err_low or "auth login" in err_low or "401" in err_low:
            return None, "gh CLI is not authenticated; run `gh auth login`"
        if "rate limit" in err_low:
            return None, "GitHub API rate-limited; reminder skipped this turn"
        return None, f"gh pr list failed ({result.returncode}): {result.stderr.strip()[:120]}"

    import json
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None, "could not parse gh JSON"
    if not payload:
        return None, None
    return payload[0].get("number"), None


def main() -> int:
    project_root_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_root_env:
        # Fail closed: don't fall back to cwd, which could be any directory.
        # posttooluse_lint.py uses the same pattern.
        print("\n[hedl] WARN: CLAUDE_PROJECT_DIR not set — stop_reminder skipped", file=sys.stderr)
        return 0
    repo_root = Path(project_root_env).resolve()

    branch = _current_branch(repo_root)
    if branch:
        pr, err = _open_pr_for_branch(branch, repo_root)
        if pr is not None:
            _print(
                f"Open PR #{pr} on {branch}. "
                f"Run `/adversarial-review` before declaring complete."
            )
        elif err is not None:
            _print(f"PR-open check unavailable: {err}")

    am_i_done = repo_root / _AM_I_DONE_REL
    if am_i_done.exists():
        _print(f"Before declaring complete, run: python3 {_AM_I_DONE_REL}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
