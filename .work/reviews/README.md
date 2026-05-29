# .work/reviews/

Adversarial review verdicts. One file per reviewed item.

## Structure

```
reviews/
  WORK-0001-requirements.json   ← task-level review
  phase-0-review.json           ← phase-level review
  self-review-001.json          ← periodic self-review
  repo-health-YYYY-MM-DD.md     ← whole-repo evaluation (/repo-health)
```

## Querying

- All blocking findings: `jq '[.[] | .blocking_findings[]]' *.json`
- All conditional unfixed: `jq '[.[] | select(.verdict=="conditional")]' *.json`
- Phase review history: `cat phase-*-review.json | jq '.verdict'`

## Retention

Task reviews: kept for the life of the phase
Phase reviews: kept permanently
Self reviews: kept permanently — these are the project's self-knowledge

## Runtime state

`queue.json` (deferred review queue, written by budget_manager.py) is runtime
state and is gitignored — it is not a review artifact.
