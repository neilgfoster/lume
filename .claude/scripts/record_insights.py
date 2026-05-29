#!/usr/bin/env python3
"""PostToolUse hook: record Hedl usage insights when [insights] enabled=true.

Reads the tool-input JSON from stdin and appends a structured event to
.work/insights/events.jsonl — but ONLY when hedl.toml [insights] enabled=true.

Recorded fields are strictly Hedl-internal metadata:
  - timestamps, tool/reviewer/command names, pass/fail counts
  - NO consumer source code, file contents, commit messages, or user names

The hook always exits 0 (failures are informational, not blocking).
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def _warn(msg: str) -> None:
    print(f"[hedl:insights] {msg}", file=sys.stderr)


def _insights_enabled(project_dir: Path) -> bool:
    hedl_toml = project_dir / "hedl.toml"
    if not hedl_toml.exists():
        return False
    try:
        with hedl_toml.open("rb") as fh:
            cfg = tomllib.load(fh)
        return bool(cfg.get("insights", {}).get("enabled", False))
    except Exception:
        return False


def _read_stdin_payload() -> dict[str, object] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        return json.loads(raw)  # type: ignore[return-value]
    except json.JSONDecodeError as exc:
        _warn(f"could not parse hook stdin: {exc}")
        return None


def _append_event(insights_dir: Path, event: dict[str, object]) -> None:
    insights_dir.mkdir(parents=True, exist_ok=True)
    events_file = insights_dir / "events.jsonl"
    with events_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _tool_to_event(payload: dict[str, object]) -> dict[str, object] | None:
    tool_name = payload.get("tool_name", "")
    ts = datetime.now(tz=timezone.utc).isoformat()

    # Map Hedl-specific tool invocations to insight events.
    # Only record the tool NAME — never inputs, outputs, or file content.
    if tool_name in ("Agent",):
        # Agent invocations may be reviewer calls; surface as reviewer_fired
        # if description contains a known reviewer name.
        description = str((payload.get("tool_input") or {}).get("description", ""))
        for reviewer in (
            "security-auditor", "simplicity-enforcer", "scope-auditor",
            "edge-case-hunter", "historian", "determinism-auditor",
            "review-dispatcher",
        ):
            if reviewer in description:
                return {"ts": ts, "type": "reviewer_fired", "reviewer": reviewer,
                        "finding_count": 0, "verdict": "unknown"}
    return None


def main() -> int:
    project_dir_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir_env:
        return 0

    project_dir = Path(project_dir_env).resolve()
    if not _insights_enabled(project_dir):
        return 0

    payload = _read_stdin_payload()
    if payload is None:
        return 0

    event = _tool_to_event(payload)
    if event is None:
        return 0

    insights_dir = project_dir / ".work" / "insights"
    try:
        _append_event(insights_dir, event)
    except OSError as exc:
        _warn(f"could not write insights event: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
