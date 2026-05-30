# evidence-checker — spike (WORK-0007)

**Run:** adversarial-review-2026-05-30-mcp-two-layer-spike
**Model:** sonnet
**Commit:** 759e953

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| medium | TS SDK asserted "equally first-class" as fact but never run (no TS artifacts); unlike HTTP it wasn't flagged unmeasured. | FIXED — demoted to doc-review-only/provisional, disclosed. |
| low | "constant per-task hop" in mild tension with steps=10 overhead ~0 (one-hop cost < jitter at 31 ms). | Already hedged; left with the noise-floor disclosure. |

Verified clean: ADR latency table matches results.json verbatim (p50); bench measures the
right comparison (two-layer vs direct, identical agent work); the PoC genuinely demonstrates
client->orch->agent->result (orchestrator is both server and client); limitations disclosed.
