# historian — security (WORK-0004)

**Run:** adversarial-review-2026-05-30-security
**Model:** sonnet
**Commit:** 1acdcb7

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| SIGNIFICANT | "No exceptions" vs grant overlay — acknowledged + tracked (WORK-0015); until then CLAUDE.md governs. | OK — explicit, no action. |
| SIGNIFICANT | Licence assertion (Apache-2.0/MIT) unverified. | FIXED — "to be confirmed in the spike". |
| SIGNIFICANT | Work-as-deterministic-service identity/trust posture unclear. | Addressed — capability/lume-agent levels cover it; Work goes through the security pipeline regardless of inference. |
| SIGNIFICANT | Audit owner not named. | FIXED — orchestrator is sole writer (§4). |
| MINOR | Per-tool blast classification incomplete. | FIXED — rubric + named high-blast tools incl. Obs delete, write_crossplane_claim. |
| MINOR | Grant mechanism depends on WORK-0015. | Noted (§6 soft-dependency). |

6-step pipeline, 4 identity levels, escalation chain all consistent with CLAUDE.md.
