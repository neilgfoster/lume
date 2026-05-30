# devil-advocate — architecture (WORK-0005)

**Run:** adversarial-review-2026-05-30-data-architecture
**Model:** sonnet
**Commit:** ce7f8ea

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| SIGNIFICANT (c1) | "replay" conflated — could re-execute side effects. | FIXED — replay is side-effect-free projection rebuild; effects via single-step check-then-act. |
| SIGNIFICANT (c1) | "one store contract" vs audit separate-trust-domain (forgery primitive). | FIXED — audit excluded from the orchestrator-callable contract; write-only emit. |
| SIGNIFICANT (c1) | Unbounded event-log growth on desktop. | FIXED via c2 — snapshots/compaction RESERVED; build-now replay is trivial at scale. |
| SIGNIFICANT (c1) | Vector store unmarked/forced decision. | FIXED — RESERVED/opt-in; deterministic search covers headline task. |
| MINOR (c1) | local-by-trust "never a hard dependency" overclaim. | FIXED — split OSS-controlled from dependency-hardness. |
| medium (c2) | Single-effect-per-step resume vs multi-effect steps. | FIXED — query-key per effect; per-effect check-then-act → WORK-0007. |
| low (c2) | Contract surface lacked ordered replay read. | FIXED — read-records-since added. |
| low (c2) | Omission-at-emit not covered by chain-and-sign. | FIXED — noted + routed to security spike. |
