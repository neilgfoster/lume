# devil-advocate — architecture (WORK-0003)

**Run:** adversarial-review-2026-05-30-agent-boundaries
**Model:** sonnet
**Commit:** 12b2b00

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| BLOCKING (c1) | create-vs-mutate: no owner for upsert; GitOps desired-state can't pre-classify. | §Provisioning/Infra | FIXED — artifact-class axis. |
| BLOCKING (c1) | No agent owns DELETE. | §2/§4 | FIXED — class owner deletes; high blast → approval. |
| BLOCKING (c1) | "add rate limiting" = new policy + existing-gateway edit in one PR; not disjoint. | CLAUDE.md headline | FIXED — both are workload manifests → Infra, one PR. |
| SIGNIFICANT (c1) | Obs alert config special-cased, undermining the axis. | §Obs | FIXED — consistent artifact-class. |
| SIGNIFICANT (c1) | Auto-remediation has no home. | §Obs | FIXED — RESERVED, advisory-to-human. |
| SIGNIFICANT (c1) | Work-item status dual-writer. | §3 | FIXED — orchestrator sole writer via transition_status. |
| SIGNIFICANT (c1) | Is Work an agent at all? | §3 | FIXED — reclassified deterministic service. |
| BLOCKING (c2) | Kind-based classification breaks on templated GitOps (Helm/Kustomize). | §scope | FIXED — domain/purpose routing. |
| SIGNIFICANT (c2) | GitOps plumbing CRs + CI have no ongoing owner. | — | FIXED — composition layer → Infra. |
| BLOCKING (c3) | "serialises edits" unspecified (recompute/render/conflict). | §routing | FIXED — serialisation contract; proof → WORK-0007. |
| SIGNIFICANT (c3) | CI create-vs-mutate temporal split (Provisioning create / Infra edit). | §4 | FIXED — Infra owns CI from first commit. |
| MINOR (c3) | Stale "by resource kind" in §6. | §6 | FIXED — domain/purpose. |
