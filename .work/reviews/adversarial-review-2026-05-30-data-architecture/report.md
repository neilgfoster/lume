# Adversarial Review — architecture (WORK-0005)

**Panel:** [scope-auditor](scope-auditor.md), [historian](historian.md), [devil-advocate](devil-advocate.md), [simplicity-enforcer](simplicity-enforcer.md), [ambiguity-hunter](ambiguity-hunter.md)
**Target:** `docs/data-architecture.md`
**Log:** adversarial-review 2026-05-30 data-architecture
**Session:** in-session
**Depth:** Standard
**Commit:** ce7f8ea
**Verdict:** cycle 1 FAIL (0 BLOCKING, ~6 SIGNIFICANT) → cycle 2 fixes → cycle 3 PASS
(simplicity-enforcer empty; dissent resolved).

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS |
| Cross-doc consistency | historian | PASS |
| Architectural bets | devil-advocate | PASS |
| Complexity | simplicity-enforcer | PASS (cycle 3 empty) |
| Requirement precision | ambiguity-hunter | PASS |

## Strengths

- Resolves the storage mechanism deferred from WORK-0002 and the context/confidentiality
  obligations from WORK-0004.
- "Event-sourced model, simplest build-now realisation" reconciles the (c) decision with
  the simplicity must-not.

## Blocking Findings

None (no cycle produced a BLOCKING).

## Significant Findings

Resolved (c1): side-effect-free replay semantics (was dangerously ambiguous); audit
excluded from the orchestrator-callable store contract (forgery-primitive collision);
event-sourcing reframed (model now, minimal build-now); vector/blob context tiers
RESERVED; confidentiality label propagates through compression; workflow event-log
growth bounded. Resolved (c2): snapshots + compaction → RESERVED (build-now = append +
replay), the core over-engineering finding; multi-effect-per-step resume (query-key per
effect, per-effect check-then-act → WORK-0007).

## Minor Findings

Resolved: tech framed as candidates pending spike; semantic opt-in trigger = explicit
flag (deterministic, not LLM); "too large" = size-check vs capability budget; contract
op-surface enumerated + ordered replay read added + update ops; context TTL invariant
(no evict of in-use context) + routed; local-vs-cloud splits OSS-controlled from
dependency-hardness; omission-at-emit routed to security spike; section-ref notation.

## Held by design (documented judgment call)

- simplicity-enforcer pushed (c2) to drop the store contract entirely. **Held:** WORK-0002
  (approved/merged) committed to the swappable store *seam* for the scale-agnostic
  principle; dropping it contradicts an approved decision. Framed as the WORK-0002 minimal
  code seam (no swap machinery build-now). **Cycle 3 simplicity-enforcer accepted this**
  as a principled held decision (empty findings).

## Next Actions

- Hand off for operator review/merge (merge = approval). 0 BLOCKING; dissent resolved.
- Downstream: storage-stack spike (append+replay, vector, contract topology, latency —
  recommend adding, → WORK-0014); WORK-0007 (multi-effect intra-step resume); WORK-0010
  (embedding + summarisation models); security spike (omission-at-emit).
