# ambiguity-hunter — architecture (WORK-0003)

**Run:** adversarial-review-2026-05-30-agent-boundaries
**Model:** sonnet
**Commit:** 12b2b00

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| high (c1) | "new vs existing" undefined observable. | §Provisioning/Infra | FIXED — axis no longer uses it. |
| high (c1) | open_pr / branch ownership undefined. | §Coding | FIXED — orchestrator owns PR/branch. |
| high (c1) | Obs-vs-Infra YAML classification. | §6 | FIXED — by domain (kind a hint). |
| high (c1) | Work-item status writer during execution. | §3 | FIXED — orchestrator sole writer. |
| low (c1) | code-vs-skeleton contingent on deferred detail. | §6 | FIXED — pinned. |
| high (c2) | Who performs the "split" of a mixed file. | §scope | FIXED — orchestrator/planner routes per-domain. |
| high (c2) | Bundling kinds (Kustomization/HelmRelease) unownable. | §scope | FIXED — routed per-domain, not owned whole. |
| high (c2) | "kind / controller" slash no precedence. | §scope | FIXED — domain/purpose is the axis. |
| medium (c2) | Obs-stack workloads straddle Infra/Obs. | tiebreaker | FIXED — deterministic obs-plane test. |
| medium (c2) | Scaffold vs class for starter non-app artifacts. | §4 | FIXED — class owner on follow-up. |
| high (c3) | Obs-stack tiebreaker "is the plane" undecidable. | tiebreaker | FIXED — functional test (collect/store/serve telemetry); ingress=Infra; sidecar routed. |
| high (c3) | Stale "by resource kind" in §6 contradicts routing. | §6 | FIXED — domain/purpose. |
| medium (c3) | CI temporal owner split. | §4 | FIXED — Infra owns CI from first commit. |
