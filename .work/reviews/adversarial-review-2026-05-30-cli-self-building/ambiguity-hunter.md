# ambiguity-hunter — requirements (WORK-0006)

**Run:** adversarial-review-2026-05-30-cli-self-building
**Model:** sonnet
**Commit:** fcea088

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| high (c1) | Protected core had no testable recogniser for "core-touching"; safe default weaker than the claim. | FIXED — interim over-approximation (all lume/-repo + core policy/config changes core-touching); non-grantable, not just human-gated. |
| high (c1) | Tier-1 grant graduation could open before the core boundary exists. | FIXED — sequenced: no Tier-1 graduation until the boundary is drawn. |
| medium (c1) | "non-self-modifiable" had no operational definition. | FIXED — fresh human-trust approval bound to the specific change; no grant/cached/idempotency satisfies it. |
| medium (c1) | lume undo stacked-changes detection conflated textual/semantic. | FIXED — undo runs full pipeline incl VALIDATE; clean-but-breaking reverts caught. |
| low (c1) | Approval carve-out not in security §3. | FIXED — added to security §3 + §6. |
| low (c1) | CLI context/undo gaps. | FIXED — context scope/label; undo mixed-effect behaviour. |
| medium (c2) | Interim recogniser ("lume/ repo") under-covers core policy in config/. | FIXED — broadened to core policy/config wherever it lives. |
