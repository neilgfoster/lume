# Adversarial Review — security (WORK-0004)

**Panel:** [security-auditor](security-auditor.md), [scope-auditor](scope-auditor.md), [ambiguity-hunter](ambiguity-hunter.md), [contradiction-finder](contradiction-finder.md), [historian](historian.md)
**Target:** `docs/security-requirements.md`
**Log:** adversarial-review 2026-05-30 security
**Session:** in-session
**Depth:** Standard
**Commit:** 1acdcb7
**Verdict:** cycle 1 FAIL → cycle 2 → cycle 3 PASS (0 BLOCKING); cycle-3 SIGNIFICANT/MINOR
applied as final polish.

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Threat model / mitigations | security-auditor | PASS (3 BLOCKING fixed) |
| Scope discipline | scope-auditor | PASS (ADOPT→recommend-pending-spike) |
| Requirement precision | ambiguity-hunter | PASS (action-class, rubric, required_trust) |
| Cross-doc consistency | contradiction-finder | PASS (all MINOR, tracked) |
| Consistency w/ prior docs | historian | PASS |

## Strengths

- Adopt-primitives / build-AI-native-defences stance is disciplined and OSS-only.
- The grant overlay keeps the permission model statically analysable.
- Every deferred mechanism is explicitly routed to the security-stack spike (§6).

## Blocking Findings

All resolved before hand-off:

- [security, c1] Prompt-injection mitigation was wrong (claimed next_action determinism
  stops injection). FIXED — reframed onto the gates; PLAN named as the surface;
  tagged-data testable rule; schema routed.
- [security, c1] SVID issued but not verified. FIXED — mutual-TLS per-call verification +
  nonce vs replay.
- [security, c1] Audit signing key co-located with orchestrator. FIXED — separate trust
  domain against a stated threat; rotation human-gated.
- [security, c2] tagged-data rule not testable; cumulative-blast undefined. FIXED — both
  stated as requirements with mechanisms routed to the spike.

## Significant Findings

Resolved (c1/c2): cumulative/workflow blast budget; approval shows real diff; context
confidentiality classification (integrity-bound, propagated, deterministic gate);
semantic output validation; denial-of-wallet limits; direct intent-field injection vector;
nonce durability vs crash-resume; ADOPT→recommend-pending-spike; audit owner named.
Resolved (c3 polish): orchestrator cross-checks `applied_effects` before cumulative
scoring; OTel emission best-effort (failures audited, Obs not sole alerting path);
`lume_context` writes go through the pipeline with identity-bound labels; `lume_status`
withholds the full approval descriptor (not just id) below required trust.

## Minor Findings

Resolved/tracked: action-class predicate + fail-closed matching; blast-radius rubric;
required_trust as a declared field; cross-tenant RESERVED; grant must carry expiry;
`lume_approve` idempotency per-identity; secrets promoted to Phase-1 blocker if a
credential-handling capability ships; CLAUDE.md "no exceptions" tracked (WORK-0015);
licences to be confirmed in the spike.

## Next Actions

- Hand off for operator review/merge (merge = approval). 0 BLOCKING.
- **Recommend adding a security-stack spike** to Phase 0 (SPIRE/OPA/signing on k3s; it
  must specify the routed mechanisms). Raise with the high-level plan (WORK-0014).
- Downstream: WORK-0011 (injection/semantic-validation red-team), WORK-0003 (per-tool
  required_trust + blast), WORK-0015 (CLAUDE.md "no exceptions").
