# security-auditor — security (WORK-0004)

**Run:** adversarial-review-2026-05-30-security
**Model:** opus
**Commit:** 1acdcb7

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| BLOCKING (c1) | Prompt-injection mitigation wrong — PLAN is inference, can be steered. | FIXED — gates + tagged-data rule + PLAN named surface. |
| BLOCKING (c1) | SVID issued but not verified per call (confused deputy). | FIXED — mutual-TLS per-call verify + socket gated. |
| BLOCKING (c1) | Audit signing key co-located; compromised orchestrator re-signs. | FIXED — separate trust domain vs stated threat. |
| SIGNIFICANT (c1) | Compositional/cumulative blast not modelled. | FIXED — workflow budget escalates approval. |
| SIGNIFICANT (c1) | Approval relies on self-reported applied_effects. | FIXED — show real diff; c3 adds cross-check. |
| SIGNIFICANT (c1) | Context leaks to cloud on escalation. | FIXED — classify + integrity-bound + deterministic gate. |
| SIGNIFICANT (c1) | Capability semantic maliciousness past signing. | FIXED — semantic output validation (BUILD). |
| SIGNIFICANT (c1) | Denial-of-wallet runaway escalation. | FIXED — rate/spend limits + circuit breaker. |
| SIGNIFICANT (c1) | SVID replay within window. | FIXED — per-call nonce. |
| BLOCKING (c2) | tagged-data not testable; cumulative-blast undefined. | FIXED — requirement stated + mechanism routed. |
| SIGNIFICANT (c2) | nonce durability vs crash-resume. | FIXED — write-ahead nonce, reissue on resume. |
| SIGNIFICANT (c2) | direct intent-field injection. | FIXED — intent sanitised/bounded. |
| SIGNIFICANT (c3) | applied_effects under-report dodges budget. | FIXED — orchestrator cross-check. |
| SIGNIFICANT (c3) | OTel path suppressible (detection gap). | FIXED — emission failures audited; Obs not sole alert path. |
| SIGNIFICANT (c3) | lume_context ingestion unauthenticated (label laundering). | FIXED — pipeline + identity-bound label. |
| SIGNIFICANT (c3) | approval descriptor leaks via lume_status. | FIXED — withhold full descriptor below trust. |
| MINOR (c3) | secrets non-blocking despite credential dependency. | FIXED — Phase-1 blocker caveat. |
| MINOR (c3) | lume_approve idempotency scope. | FIXED — per-identity. |

Cycle 3: 0 BLOCKING — all mechanisms routed to the security-stack spike (§6).
