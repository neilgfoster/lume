# historian — spike (WORK-0007)

**Run:** adversarial-review-2026-05-30-mcp-two-layer-spike
**Model:** sonnet
**Commit:** 759e953

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| SIGNIFICANT | mcp SDK license not stated (CLAUDE.md principle 10 OSS-only). | FIXED — MIT, stated. |
| SIGNIFICANT | "Confirms a WORK-0005 assumption" mis-attributed (persistent sessions is WORK-0002 orchestrator-design). | FIXED — corrected to WORK-0002 §3. |
| MINOR | ADR header differs from .work/decisions/README.md narrative format. | Kept schema-compliant form (README format conflicts with the enforced schema — project doc inconsistency). |

Consistent with CLAUDE.md two-layer pattern, MCP-first, deterministic-over-inference; no
prior ADR contradicted (ADR-001 is the first project ADR).
