# devil-advocate — architecture (WORK-0002)

**Run:** adversarial-review-2026-05-30-architecture
**Model:** sonnet
**Commit:** eefa2e1

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| BLOCKING | Halt-and-surface "safe by construction" is false for SDLC — push/PR are non-reconcilable, non-gated, visible partial state. | §5 vs CLAUDE.md vision | FIXED — honest scope; effects left for operator cleanup because visible+non-destructive; surface lists them. |
| BLOCKING | Idempotency asserted by fiat vs "no durable in-process state"; PR creation not naturally idempotent. | §3, §5 | FIXED — write-ahead step-intent records + check-then-act; proof routed to WORK-0007. |
| SIGNIFICANT (cycle 2) | "List partial effects" had no source contract. | §5 | FIXED — typed applied_effects[] on capability result (§3/§4), reported not inferred. |
| SIGNIFICANT (cycle 2) | Write-ahead record not specified to carry deterministic identity for check-then-act. | §3 | FIXED — record carries computed branch/PR identity; precondition → WORK-0003/0007. |

Also pressure-tested (cycle 1, accepted as operator decisions, not findings): planner-as-
capability and stateless-over-store flagged as generality-before-2nd-instance — resolved
by the "design general, build simple" build-now scoping.
