#!/usr/bin/env python3
"""PostToolUse hook: lint a Python file after Claude edits it.

Reads the tool-input JSON from stdin, extracts `file_path`, and runs
`ruff check` on it if the path is inside the project and ends in `.py`.

Hardenings applied here:

- SEC2 — ruff invocation uses `--` so a file path beginning with `-`
  cannot inject a ruff option flag.
- SEC13 — file_path is resolved to an absolute path and must be inside
  `$CLAUDE_PROJECT_DIR`; paths outside the project are silently skipped.
- CE1 / OP3 — failures are NOT silenced with `2>/dev/null`. Missing
  python3, missing ruff, or a malformed stdin payload all produce a
  one-line `[hedl:postedit] …` warning on stderr so the operator can
  see what's broken.
- EC14 — ruff's exit code is preserved; output is not piped to `head`
  in a way that masks a non-zero exit.
- FE5 — implemented in Python rather than inline bash so the hook is
  portable to Windows (no bash, no `[[`).

The hook always exits 0 (a failed lint is informational, not a block).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_MAX_OUTPUT_LINES = 40
_RUFF_TIMEOUT_SECONDS = 10


def _warn(msg: str) -> None:
    print(f"[hedl:postedit] {msg}", file=sys.stderr)


def _read_file_path() -> str | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        _warn(f"could not parse hook stdin as JSON: {exc}")
        return None
    return (payload.get("tool_input") or {}).get("file_path") or None


def main() -> int:
    file_path_raw = _read_file_path()
    if not file_path_raw:
        return 0

    project_root_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_root_env:
        _warn("CLAUDE_PROJECT_DIR is unset; skipping lint")
        return 0
    project_root = Path(project_root_env).resolve()

    # Resolve and bound the path to the project (SEC13).
    try:
        target = Path(file_path_raw).resolve()
    except (OSError, RuntimeError) as exc:
        _warn(f"could not resolve {file_path_raw!r}: {exc}")
        return 0

    try:
        target.relative_to(project_root)
    except ValueError:
        # Path lives outside the project — skip silently.
        return 0

    if target.suffix != ".py":
        return 0
    if not target.exists():
        return 0

    ruff = shutil.which("ruff")
    if not ruff:
        _warn("ruff not on PATH; install ruff to enable post-edit lint")
        return 0

    try:
        result = subprocess.run(
            [ruff, "check", "--select", "E,F,W", "--quiet", "--", str(target)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=_RUFF_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _warn(f"ruff timed out after {_RUFF_TIMEOUT_SECONDS}s")
        return 0
    except OSError as exc:
        _warn(f"could not run ruff: {exc}")
        return 0

    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        # Mark output unambiguously as hook-sourced (OP7).
        for line in output.splitlines()[:_MAX_OUTPUT_LINES]:
            print(f"[hedl:postedit] {line}")

    if result.returncode != 0:
        _warn(f"ruff exited {result.returncode} on {target.relative_to(project_root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
