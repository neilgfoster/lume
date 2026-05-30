# contradiction-finder — security (WORK-0004)

**Run:** adversarial-review-2026-05-30-security
**Model:** sonnet
**Commit:** 1acdcb7

## Findings

All MINOR (no hard contradiction):

| Finding | Status |
|---------|--------|
| "static, never mutated" vs capability "low until reviewed" trust change. | FIXED — review-to-trusted transition realised as an audited grant. |
| "LLM never decides control flow" overstated vs PLAN being inference. | FIXED — mitigation reframed onto the gates; PLAN named as surface. |
| CLAUDE.md "no exceptions" vs grant overlay. | Acknowledged + tracked WORK-0015. |
| Obs delete path omitted from high-blast deletes. | FIXED — Obs delete + write_crossplane_claim listed high. |

Verified clean: no-self-approval holds; must-not #1 vs exfiltration consistent;
applied_effects/audit/approval-gating align with orchestrator design; Work-as-service
bypasses only PLAN/REFINE, not the security pipeline.
