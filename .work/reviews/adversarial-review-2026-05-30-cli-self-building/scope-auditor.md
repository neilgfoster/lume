# scope-auditor — requirements (WORK-0006)

**Run:** adversarial-review-2026-05-30-cli-self-building
**Model:** opus
**Commit:** fcea088

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| SIGNIFICANT | §4 over-specified enforcement (action-class predicates, OPA, precise core enumeration) for a Phase-0 requirements doc. | FIXED — core stated conceptually; enforcement softened to a requirement + routed to the security spike; precise enumeration deferred to WORK-0014. |
| SIGNIFICANT | Internal tension: §4 enumerates the core while §5 defers its exact boundary. | FIXED — §4 is the conceptual core; precise boundary deferred; interim over-approximation added. |

CLI surface (intent-first + thin verbs) is the minimal surface; rich tree correctly RESERVED.
