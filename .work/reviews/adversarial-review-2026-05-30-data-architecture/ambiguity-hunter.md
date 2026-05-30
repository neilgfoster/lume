# ambiguity-hunter — architecture (WORK-0005)

**Run:** adversarial-review-2026-05-30-data-architecture
**Model:** sonnet
**Commit:** ce7f8ea

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| high (c1) | Semantic "opt-in" trigger undefined (who decides). | FIXED — explicit flag on the retrieval request; deterministic, not LLM. |
| medium (c1) | "too large" summarisation threshold undefined. | FIXED — size-check vs capability context budget; value is tuning (§6). |
| medium (c1) | Context TTL/eviction unrouted; resume-correctness gap. | FIXED — invariant (no evict of in-use context) + routed to spike. |
| medium (c1) | "one store contract" surface not described. | FIXED — op-surface enumerated. |
| low (c1) | Confidentiality ceiling ordering. | Cross-ref security §1 (label ordering defined there). |
| low (c1) | Snapshot cadence deferral. | Sound deferral (now RESERVED). |
