# security-auditor — spike (WORK-0007)

**Run:** adversarial-review-2026-05-30-mcp-two-layer-spike
**Model:** opus
**Commit:** 759e953

## Findings

All findings are **PoC-acceptable** (disposable spike code); flagged so they are not
cargo-culted into Phase 1. Addressed by an explicit "PoC omits the security pipeline /
input bounds — don't cargo-cult" note in the ADR + README (code left as throwaway).

| Severity | Finding | Disposition |
|----------|---------|-------------|
| SIGNIFICANT | Unbounded `steps` from caller -> unbounded agent fan-out (DoS if copied to prod). | Noted; Phase-1 must clamp. |
| SIGNIFICANT | Unbounded argv ints in bench.py. | PoC-acceptable. |
| MINOR | int() on agent text w/o try/except (info-disclosure if copied). | Noted; Phase-1 typed validation. |
| MINOR | subprocess path from __file__ (safe now; don't generalise to user input). | Noted. |
| MINOR | No identity/blast-radius/audit on tool calls. | Noted; Phase-1 must enforce WORK-0004 pipeline. |
