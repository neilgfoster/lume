# Adversarial Review — architecture (WORK-0002)

**Panel:** [scope-auditor](scope-auditor.md), [historian](historian.md), [devil-advocate](devil-advocate.md), [simplicity-enforcer](simplicity-enforcer.md), [future-engineer](future-engineer.md)
**Target:** `docs/orchestrator-design.md`
**Log:** adversarial-review 2026-05-30 architecture
**Session:** in-session
**Depth:** Standard
**Commit:** eefa2e1
**Verdict:** cycle 1 FAIL → cycle 2 (fixes) → cycle 3 PASS (zero BLOCKING).

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS (cycle 2 clean) |
| Cross-doc consistency | historian | PASS (MINORs addressed) |
| Architectural bets | devil-advocate | PASS (BLOCKING fixed) |
| Complexity | simplicity-enforcer | PASS (resolved via design-general/build-simple) |
| Interface contract | future-engineer | PASS (BLOCKING fixed cycle 3) |

## Strengths

- Operator decision "design general, build simple" cleanly reconciles the platform
  vision with the simplicity must-not; build-now vs RESERVED marked throughout.
- Honest failure model: halt-and-surface scope corrected; partial effects acknowledged.
- Deterministic core preserved; inference confined to PLAN/REFINE.

## Blocking Findings

All resolved before approval:

- [devil-advocate, cycle 1] Halt-and-surface safety premise false for SDLC (push/PR are
  non-reconcilable, non-gated, visible). FIXED — §5 honest scope + list applied effects.
- [devil-advocate, cycle 1] Idempotency-by-fiat vs "no in-process state." FIXED — §3
  write-ahead step-intent records + idempotent/check-then-act; proof routed to WORK-0007.
- [future-engineer, cycle 1] Missing error shape, approval correlation, work/lifecycle
  discriminator. FIXED — common outcome envelope, approval descriptor, `intent_kind`.
- [future-engineer, cycle 2] No per-outcome field-presence rule; `reason_code` no value
  space. FIXED cycle 2 — field-presence rule + open-additive code set; confirmed cycle 3.

## Significant Findings

Resolved in-PR: scope creep (template machinery → RESERVED); premature abstraction
(planner inline, embedded store, no registry — build-now); `required_trust` registry
coupling (hardcoded per capability build-now); class 1/2 discrimination (Phase 1 blocks
on WORK-0011); applied-effects contract + deterministic resume identity (→ WORK-0003);
contract clarifications (idempotency scope/conflict, plan_ref dereference, since_token
interop, approval_id timing). `needs_approval` orphan code removed (cycle 3).

## Minor Findings

historian: escalation notation clarified; CLAUDE.md vision/OSS/autonomy tensions already
tracked by WORK-0015. future-engineer: items[] typed by scope, total-presence rule,
field-presence dry_run clause (cycle 3), context constraints → WORK-0005. All addressed
or correctly deferred with forward references.

## Next Actions

- Zero BLOCKING — proceed once Neil approves the doc.
- Downstream obligations recorded: WORK-0003 (capability result contract incl.
  applied_effects + idempotency), WORK-0005 (state store + context constraints),
  WORK-0007 (MCP surface, mid-workflow-failure-after-push, non-idempotent crash-safety),
  WORK-0011 (class 1/2 discrimination), WORK-0015 (CLAUDE.md reconciliation).
