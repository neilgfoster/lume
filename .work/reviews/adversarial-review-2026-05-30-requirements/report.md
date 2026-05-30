# Adversarial Review — requirements (WORK-0001 / PR #5)

**Panel:** [scope-auditor](scope-auditor.md) (mandatory), [ambiguity-hunter](ambiguity-hunter.md), [contradiction-finder](contradiction-finder.md)
**Target:** `docs/requirements.md`
**Log:** adversarial-review 2026-05-30 requirements
**Session:** in-session
**Depth:** Standard
**Commit:** 32a153b
**Verdict:** CONDITIONAL — findings actioned in-PR; doc revised, awaiting operator re-approval.

## Dimension Scores

| Dimension | Persona | Score |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS (no findings) |
| Clarity / testability | ambiguity-hunter | CONDITIONAL (precision gaps, fixed) |
| Internal + cross-doc consistency | contradiction-finder | CONDITIONAL (governance conflict, fixed) |

## Strengths

- Stays at requirements altitude; defers mechanisms to design/ADRs (scope-auditor confirmed).
- Frames every tech choice as a swappable default, not a commitment.
- Includes an explicit phase-discipline note containing future-scope vision.

## Blocking Findings

- [contradiction-finder] **Two contradictory governing documents.** `docs/requirements.md`
  declared itself authoritative over `CLAUDE.md` but did not change it, while `CLAUDE.md`
  states its own instructions override. Corroborated independently by ambiguity-hunter.
  Evidence: requirements.md preamble "this document is the corrected, broader intent" vs
  CLAUDE.md line 1 "An AI-native internal developer platform (IDP)" + "instructions OVERRIDE".
  **Status: UPHELD → FIXED.** Reframed preamble to an interim governance rule; reconciliation
  tracked as WORK-0015; supersession no longer asserted present-tense.

## Significant Findings

- [contradiction-finder] Earned-autonomy "guardrails can be relaxed" vs CLAUDE.md
  "High always requires human approval — no exceptions." **FIXED:** recorded as deliberate
  revision, reconciled in WORK-0015.
- [contradiction-finder] No-lock-in hard line vs HEDL listed as "a must." **FIXED:** HEDL
  reframed as an acknowledged bootstrap-period dependency; fate is an open question.
- [ambiguity-hunter] Headline metric "more" had no unit; "spend roughly flat" no band.
  **FIXED:** unit = delivered work items / merged PRs per month vs baseline; "fixed budget"
  = no new paid spend beyond the Claude Pro plan. Numeric targets remain deferred.
- [ambiguity-hunter] "clean contract" undefined (load-bearing, used 5×). **FIXED:** one-line
  working definition added.
- [ambiguity-hunter] "genuinely needed" (inference rule) unanchored. **FIXED:** anchored to
  CLAUDE.md's concrete rule "if a function can do it, an LLM must not."
- [ambiguity-hunter] "grunt work" undefined (offload thesis depends on it). **FIXED:** defined
  as low-novelty/deterministic tasks a local model can complete within validation limits.

## Minor Findings

- [ambiguity-hunter] "until the balance feels right" subjective. **FIXED:** restated as a
  testable system requirement (any subset offloadable/revocable at any time).
- [contradiction-finder] "no permanent constraints" vs hard-line naming K8s/Ollama. **FIXED:**
  clarified the hard line is on the principle; named technologies stay swappable.
- [contradiction-finder] Status "approved" while under review. **REBUTTED then addressed:**
  operator approval satisfies acceptance criterion 2 (a distinct gate from adversarial review);
  status reset to "in review" because the doc was revised post-approval.
- [ambiguity-hunter] time-to-done conflation, self-built attribution, "much better" axis,
  "realistic timeframe". Partially addressed ("reliability" dimension named); remainder left at
  requirements altitude — fuller quantification would cross into architecture (criterion 3),
  which scope-auditor confirmed.

## Next Actions

- CONDITIONAL → revisions applied; proceed once Neil re-approves the revised doc.
- `CLAUDE.md` reconciliation tracked as **WORK-0015** — must not be assumed done.
