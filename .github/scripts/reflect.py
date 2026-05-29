#!/usr/bin/env python3
"""reflect.py — deterministic aggregator for Hedl usage insights.

Reads .work/insights/events.jsonl and produces a deterministic metrics
summary at .work/insights/metrics.json.  The aggregation is pure Python
with no LLM involvement.  The /reflect command then points the existing
review agents (existential-challenger, drift-detector, agent-evaluator)
at the metrics JSON to synthesise improvement proposals.

Usage:
  reflect.py --work-dir .work                       # aggregate + write metrics
  reflect.py --work-dir .work --print               # print metrics JSON to stdout
  reflect.py --schema                               # machine-readable CLI spec
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any

CLI_SPEC: dict[str, Any] = {
    "name": "reflect",
    "script": "reflect.py",
    "description": "Aggregate Hedl usage insights into a deterministic metrics summary.",
    "invocation": "python3 .github/scripts/reflect.py",
    "commands": [
        {
            "name": "default",
            "description": "Aggregate events.jsonl into metrics.json",
            "args": [
                {
                    "flag": "--work-dir",
                    "type": "str",
                    "required": False,
                    "help": "Path to .work directory (default: .work)",
                },
                {
                    "flag": "--print",
                    "type": "bool",
                    "required": False,
                    "help": "Print metrics JSON to stdout instead of writing file",
                },
            ],
            "output": (
                "Writes .work/insights/metrics.json and exits 0. "
                "Exits 2 if insights are not enabled or no events exist."
            ),
        },
    ],
}

_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "ts", "type",
    # gate_run fields
    "tier", "checks", "overridden",
    # reviewer_fired fields
    "reviewer", "finding_count", "verdict",
    # command_used fields
    "command",
})


def _load_events(events_path: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not os.path.exists(events_path):
        return events
    with open(events_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def aggregate(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically aggregate raw events into a metrics dict.

    All computation is pure arithmetic — no LLM involved.
    """
    gate_runs: list[dict[str, Any]] = []
    reviewer_events: list[dict[str, Any]] = []
    command_events: list[dict[str, Any]] = []

    for ev in events:
        t = ev.get("type")
        if t == "gate_run":
            gate_runs.append(ev)
        elif t == "reviewer_fired":
            reviewer_events.append(ev)
        elif t == "command_used":
            command_events.append(ev)

    # Gate check pass/fail rates
    check_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0, "skip": 0})
    overrides: dict[str, int] = defaultdict(int)
    for gr in gate_runs:
        for check, result in gr.get("checks", {}).items():
            if result in check_stats[check]:
                check_stats[check][result] += 1
        for ov in gr.get("overridden", []):
            overrides[ov] += 1

    # Reviewer stats
    reviewer_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"fired": 0, "total_findings": 0, "verdicts": defaultdict(int)}
    )
    for rev in reviewer_events:
        name = rev.get("reviewer", "unknown")
        reviewer_stats[name]["fired"] += 1
        reviewer_stats[name]["total_findings"] += rev.get("finding_count", 0)
        v = rev.get("verdict", "unknown")
        reviewer_stats[name]["verdicts"][v] += 1

    # Serialise reviewer defaultdicts so output is plain JSON
    reviewer_out: dict[str, Any] = {}
    for name, stats in reviewer_stats.items():
        reviewer_out[name] = {
            "fired": stats["fired"],
            "total_findings": stats["total_findings"],
            "verdicts": dict(stats["verdicts"]),
            "finding_rate": (
                round(stats["total_findings"] / stats["fired"], 2)
                if stats["fired"] > 0 else 0.0
            ),
        }

    # Command usage counts
    command_counts: dict[str, int] = defaultdict(int)
    for ce in command_events:
        command_counts[ce.get("command", "unknown")] += 1

    # Tier distribution
    tier_counts: dict[str, int] = defaultdict(int)
    for gr in gate_runs:
        tier_counts[gr.get("tier", "unknown")] += 1

    return {
        "event_count": len(events),
        "gate_runs": len(gate_runs),
        "check_stats": {k: dict(v) for k, v in sorted(check_stats.items())},
        "overrides": dict(sorted(overrides.items())),
        "reviewer_stats": reviewer_out,
        "command_counts": dict(sorted(command_counts.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
    }


def main() -> int:
    if "--schema" in sys.argv:
        print(json.dumps(CLI_SPEC, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Aggregate Hedl usage insights")
    parser.add_argument("--work-dir", default=".work", help="Path to .work directory")
    parser.add_argument("--print", action="store_true", dest="print_only",
                        help="Print to stdout instead of writing file")
    args = parser.parse_args()

    work_dir = args.work_dir
    events_path = os.path.join(work_dir, "insights", "events.jsonl")
    metrics_path = os.path.join(work_dir, "insights", "metrics.json")

    events = _load_events(events_path)
    if not events:
        print("No insight events found — run with [insights] enabled=true in hedl.toml first.",
              file=sys.stderr)
        return 2

    metrics = aggregate(events)

    if args.print_only:
        print(json.dumps(metrics, indent=2))
        return 0

    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
        fh.write("\n")

    print(f"Metrics written to {metrics_path}  ({metrics['event_count']} events aggregated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
