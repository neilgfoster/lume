# historian — architecture (WORK-0003)

**Run:** adversarial-review-2026-05-30-agent-boundaries
**Model:** sonnet
**Commit:** 12b2b00

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| SIGNIFICANT (c1) | "observe" reassigned from Infra to Obs vs CLAUDE.md without acknowledgement. | CLAUDE.md "Infra: scale, debug, observe" vs doc §Obs | FIXED — explicit revision note + WORK-0015. |
| MINOR (c1) | Escalation notation unclear vs orchestrator design. | cross-cutting contract | FIXED — matched wording. |
| SIGNIFICANT (c2) | Work-as-deterministic-service: does it still VALIDATE/ESCALATE? | §3 | FIXED — specified ACT→VALIDATE only, no PLAN/REFINE/escalation. |
| SIGNIFICANT (c2) | Orchestrator-owns-PR stated but not grounded in orchestrator design §1. | cross-cutting contract | FIXED — grounded in orchestrator design §3; §1-list gap → WORK-0015. |
| MINOR (c2) | Artifact-class axis presented as established. | §scope | FIXED — "clarifies (does not restate)". |
| MINOR (c2) | "first registered capabilities" — registry RESERVED. | header | FIXED — "first capabilities". |

New cross-doc tensions all acknowledged and tracked (WORK-0015 extended to 6 items).
