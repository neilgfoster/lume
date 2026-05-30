# historian — requirements (WORK-0006)

**Run:** adversarial-review-2026-05-30-cli-self-building
**Model:** sonnet
**Commit:** fcea088

## Findings

| Severity | Finding | Status |
|----------|---------|--------|
| SIGNIFICANT | "non-grantable" core class asserted but security §2 has no mechanism to mark a class non-grantable. | FIXED — added to security §3 carve-out + §6 spike deliverable (bidirectional). |

Verified consistent: CLI maps to the 5 MCP tools (undo = lume_task sugar, not a 6th);
approval gates align with security §3; rollback via GitOps revert aligns with the
GitOps principle + halt-and-surface; no-self-approval aligns with the identity model;
the constitutional core is a consistent safety floor for the autonomy arc (with the
Phase-5 reconciliation note added).
