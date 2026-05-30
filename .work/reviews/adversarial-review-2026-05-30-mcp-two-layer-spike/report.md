# Adversarial Review — architecture/spike (WORK-0007)

**Panel:** [scope-auditor](scope-auditor.md), [security-auditor](security-auditor.md), [evidence-checker](evidence-checker.md), [devil-advocate](devil-advocate.md), [historian](historian.md)
**Target:** `spikes/mcp-two-layer/` + `.work/decisions/ADR-001-mcp-two-layer.md`
**Log:** adversarial-review 2026-05-30 mcp-two-layer-spike
**Session:** in-session
**Depth:** Standard
**Commit:** 759e953
**Verdict:** PASS (0 BLOCKING). GO verdict sound; ADR claims bounded/corrected in one cycle.

## Dimension Scores

| Dimension | Persona | Final |
|-----------|---------|-------|
| Scope discipline | scope-auditor | PASS (clean) |
| Security (PoC) | security-auditor | PASS (PoC-acceptable; don't-cargo-cult noted) |
| Evidence integrity | evidence-checker | PASS (after evidence + TS-SDK fixes) |
| GO soundness | devil-advocate | PASS (GO bounded to local stdio) |
| Cross-doc consistency | historian | PASS (license + attribution fixed) |

## Strengths

- Genuine working PoC: orchestrator is both MCP server and MCP client of the agent.
- Bench methodology sound (two-layer vs direct baseline isolates the one hop).
- Trivial agent tool is the *right* choice for isolating transport cost.

## Blocking Findings

None.

## Significant Findings

Resolved in-PR:
- **TS SDK overclaim** (evidence-checker + devil-advocate + scope-auditor): stated as
  "equally first-class" fact but never run, while "TS SDK evaluated" was an acceptance
  criterion. FIXED — demoted to doc-review-only/provisional, disclosed.
- **Latency GO not bounded to transport** (devil-advocate): ~2-3 ms is stdio/local; k8s
  agents-as-pods (WORK-0008's question) would differ. FIXED — performance GO bounded to
  the local stdio profile; enterprise-scale gated on WORK-0008.
- **mcp SDK license unstated** (historian, OSS-only principle). FIXED — MIT, stated.
- **"Confirms a WORK-0005 assumption"** mis-attributed (historian). FIXED — it is WORK-0002.
- **Pre-fix evidence mismatch** (caught by the dispatcher): results.json (single noisy run,
  9.8 ms) contradicted the ADR. FIXED before the panel — canonical 200-iter suite, p50,
  quoted verbatim.

## Minor Findings

Resolved/noted: fan-out "linear scaling" relabelled a hypothesis (sequential single-agent
only; retest WORK-0008); large-payload double-marshalling added to deferred; PoC omits the
security pipeline + input bounds by design — don't-cargo-cult note added to ADR + README
(security-auditor's findings are all PoC-acceptable). ADR kept in schema-compliant form
(the `.work/decisions/README.md` narrative format conflicts with the enforced schema — a
project doc inconsistency, not this ADR's error).

## Next Actions

- Hand off for operator review/merge (merge = approval). 0 BLOCKING.
- WORK-0008 (kagent) must resolve agent transport (stdio child vs networked pod) and
  multi-agent fan-out — the two items the performance GO is gated on.
