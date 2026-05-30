# Adversarial Review — architecture (WORK-0003)

**Panel:** [scope-auditor](scope-auditor.md), [historian](historian.md), [devil-advocate](devil-advocate.md), [ambiguity-hunter](ambiguity-hunter.md)
**Target:** `docs/agent-boundaries.md`
**Log:** adversarial-review 2026-05-30 agent-boundaries
**Session:** in-session
**Depth:** Standard
**Commit:** 12b2b00
**Verdict:** cycle 1 FAIL → cycle 2 → cycle 3 → fixes applied (3-cycle cap reached). 0 contested
design remaining; cycle-3 fixes are precision/wording.

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS (clean cycle 1) |
| Cross-doc consistency | historian | PASS (fixes applied) |
| Boundary correctness | devil-advocate | PASS (axis re-resolved; serialisation contract specified) |
| Boundary precision | ambiguity-hunter | PASS (domain routing + deterministic tiebreakers) |

## Strengths

- Operator decision "artifact-class split" fixed the create-vs-mutate collisions (upsert,
  delete, mixed-PR) the original axis could not own.
- Each cycle converged (3→1→1 BLOCKING), narrowing to mechanism precision.

## Blocking Findings

All resolved before hand-off:

- [devil, cycle 1] create-vs-mutate had no owner for upsert/delete and split the headline
  "add rate limiting" PR. FIXED — artifact-class partition (operator decision).
- [devil, cycle 2] kind-based classification breaks on templated GitOps (Helm/Kustomize).
  FIXED — classification by domain/purpose; planner routes; tiebreakers added.
- [devil, cycle 3] "orchestrator serialises edits" unspecified. FIXED — serialisation
  contract (sequential dispatch, read-current-head, VALIDATE on merged/re-rendered file,
  apply failure is a deterministic finding); proof routed to WORK-0007.

## Significant Findings

Resolved: Work reclassified as deterministic service (ACT→VALIDATE only); orchestrator
sole writer of work-item status; auto-remediation RESERVED; observe→Obs + write_gitops_config
split + Work-as-service routed to WORK-0015; GitOps plumbing/CI → Infra (deployment layer);
CI temporal split removed (Infra owns CI from first commit); obs-plane workload tiebreaker
given a deterministic test; orchestrator-owns-PR grounded in orchestrator design §3.

## Minor Findings

Resolved: escalation notation matched to orchestrator design; "first capabilities"
(registry RESERVED); diagnose vs get_health tightened; stale "by resource kind" wording
struck from §6 and Obs.

## Next Actions

- Hand off for operator review/merge (merge = approval). 3-cycle cap reached; cycle-3
  fixes applied are precision-level, not contested design.
- Downstream: WORK-0007 (serialisation + non-idempotent crash-safety proof), WORK-0010
  (model assignments), WORK-0011 (VALIDATE internals), WORK-0004 (per-tool trust/blast),
  WORK-0012/0013 (scaffold), WORK-0015 (CLAUDE.md reconciliation, now 6 items).
