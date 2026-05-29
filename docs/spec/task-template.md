# Task template

Tasks live in `.work/work.json`, not as markdown files. This template shows the
required fields for a work item.

```json
{
  "id": "WORK-XXXX",
  "title": "Short imperative description",
  "workstream": "WS-ARCH",
  "status": "todo",
  "epic": "epic-001",
  "acceptance_criteria": [
    "criterion 1 — specific, verifiable",
    "criterion 2 — specific, verifiable"
  ],
  "dependencies": [],
  "created_date": "YYYY-MM-DD",
  "notes": ""
}
```

## Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | WORK-NNNN, sequential |
| `title` | Yes | Imperative, ≤72 chars |
| `workstream` | Yes | WS-PLAN, WS-REQ, WS-TECH, or WS-ARCH |
| `status` | Yes | todo, in_progress, complete, blocked |
| `epic` | No | Reference to `docs/spec/epics/epic-NNN.md` |
| `acceptance_criteria` | Yes | List of verifiable conditions |
| `dependencies` | No | List of WORK-IDs that must complete first |
| `created_date` | Yes | ISO 8601 |
| `notes` | No | Context, decisions, links |

## Workstream selection

| Workstream | When to use |
|-----------|-------------|
| `WS-PLAN` | Scope, phase definitions, backlog grooming, project setup |
| `WS-REQ` | Gathering or refining requirements, user stories |
| `WS-TECH` | Spikes, technology choices, proof-of-concept work |
| `WS-ARCH` | Design decisions, ADRs, structural changes |

---

*See [docs/spec-pipeline.md](../../docs/spec-pipeline.md) for the full pipeline.*
