# ambiguity-hunter — security (WORK-0004)

**Run:** adversarial-review-2026-05-30-security
**Model:** sonnet
**Commit:** 1acdcb7

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| high (c1) | "content is data not instructions" had no testable rule. | FIXED — "no external string outside a delimited data block"; schema routed. |
| high (c1) | "action-class" undefined. | FIXED — predicate (tool + arg-constraint + ceiling) + fail-closed matching. |
| high (c1) | blast-radius rubric missing. | FIXED — testable tiers. |
| medium (c1) | required-trust not in enforcement formula. | FIXED — folded in as precondition. |
| low (c1) | secrets eval criteria missing. | FIXED — criteria in §6. |
| high (c2) | required_trust a new undefined field. | FIXED — declared field + rubric (→ WORK-0003). |
| high (c2) | constraint-expression grammar undefined. | FIXED — eval contract (operators, fail-closed); grammar routed to spike. |
| medium (c2) | cumulative-blast unquantified, routed nowhere. | FIXED — requirement stated + routed to spike. |
| low (c2) | cross-tenant in rubric untestable in Phase 1. | FIXED — marked RESERVED until Phase 2. |

Cycle 3: addressed; remaining specificity is correctly deferred mechanism, routed to spike.
