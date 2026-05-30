# contradiction-finder — requirements (WORK-0001)

**Run:** adversarial-review-2026-05-30-requirements
**Model:** sonnet
**Commit:** 32a153b

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| BLOCKING | Two contradictory governing documents: requirements.md declares itself authoritative over CLAUDE.md but does not change it; CLAUDE.md says its own instructions override. | requirements.md preamble vs CLAUDE.md line 1 "IDP" + "instructions OVERRIDE"; PR #5 does not touch CLAUDE.md | FIXED — interim governance rule; reconciliation tracked as WORK-0015. |
| SIGNIFICANT | Earned-autonomy "guardrails can be relaxed" vs CLAUDE.md "High always requires human approval — no exceptions." | requirements.md §3 postures vs CLAUDE.md security model | FIXED — recorded as deliberate revision, reconciled in WORK-0015. |
| SIGNIFICANT | No-lock-in hard line vs HEDL listed as "a must" without a swap contract. | requirements.md §3.1 vs §5 "HEDL — a must, for now" | FIXED — HEDL reframed as acknowledged bootstrap-period dependency. |
| MINOR | "no permanent technology constraints" vs hard line naming K8s/Ollama. | requirements.md §5 vs §3.1 | FIXED — clarified hard line is on the principle. |
| MINOR | Status "approved" while submitted for adversarial review. | requirements.md header vs open PR #5 | REBUTTED (distinct gates) then addressed — status reset to "in review" after revision. |

The BLOCKING finding was corroborated independently by ambiguity-hunter, raising confidence.
Resolution does not silently drop the contradictions — it records the intentional revisions
and tracks the CLAUDE.md edit as WORK-0015.
