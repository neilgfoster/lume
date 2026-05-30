# Adversarial Review — requirements (WORK-0006)

**Panel:** [scope-auditor](scope-auditor.md), [ambiguity-hunter](ambiguity-hunter.md), [contradiction-finder](contradiction-finder.md), [historian](historian.md)
**Target:** `docs/cli-requirements.md`
**Log:** adversarial-review 2026-05-30 cli-self-building
**Session:** in-session
**Depth:** Standard
**Commit:** fcea088
**Verdict:** cycle 1 FAIL (0 BLOCKING, ~4 SIGNIFICANT/high) → cycle 2 PASS (0 BLOCKING;
all MINOR cross-doc-tracking residuals closed bidirectionally).

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS |
| Requirement precision / safety | ambiguity-hunter | PASS |
| Cross-doc consistency | contradiction-finder | PASS |
| Architectural consistency | historian | PASS |

## Strengths

- The constitutional-core / two-tier self-modification model closes a real
  self-referential safety hole in the earned-autonomy design.
- Intent-first CLI stays consistent with the 5-tool surface (undo = lume_task sugar).

## Blocking Findings

None.

## Significant Findings

Resolved (c1): the protected-core safety claim was unenforceable (no recogniser for
"core-touching") and §4/§5 were internally in tension → added an **interim
over-approximation** (all `lume/`-repo + core policy/config changes are core-touching
until WORK-0014 draws the boundary) and **sequenced** it (no Tier-1 grant graduation
before then); operationally defined "non-self-modifiable" (fresh human approval bound to
the change; no grant/cached/idempotency); softened enforcement to a requirement + routed
the non-grantable mechanism to the security spike. (scope-auditor's over-specification
concern addressed by the same softening.)

## Minor Findings

Resolved: reconciliation notes (Tier-2 bounds CLAUDE.md Phase-5; the core's "no
exceptions" is permanent and WORK-0015 must preserve it); the core carve-out + preservation
obligation made **bidirectional** — recorded in security-requirements.md §3/§6 and
WORK-0015, not only cross-referenced from here; interim recogniser broadened to cover core
policy in `config/`; Tier-1 graduation line given an inline pointer; `lume undo` confirmed
not a 6th tool, mixed-effect behaviour + full-pipeline VALIDATE specified; `lume context`
scope values + confidentiality-label visibility.

## Next Actions

- Hand off for operator review/merge (merge = approval). 0 BLOCKING.
- This PR also makes a small consistency edit to the merged `security-requirements.md`
  (adds the non-grantable core carve-out to §3/§6) to close a cross-doc contradiction —
  intentional, flagged in the PR.
- Downstream: WORK-0014 (governance item to draw the precise protected-core boundary),
  WORK-0004/security spike (non-grantable enforcement), WORK-0015 (preserve the permanent
  core absolute).
