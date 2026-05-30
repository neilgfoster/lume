# ambiguity-hunter — requirements (WORK-0001)

**Run:** adversarial-review-2026-05-30-requirements
**Model:** sonnet
**Commit:** 32a153b

## Findings

| Severity | Finding | Evidence | Status |
|----------|---------|----------|--------|
| BLOCKING | Headline metric "more" has no unit of measure — unfalsifiable. | "builds and delivers more on the same budget" | FIXED — unit = delivered work items / merged PRs per month vs baseline. |
| BLOCKING | "spend stays roughly flat" has no tolerance band. | "Spend stays roughly flat" | FIXED — "no new paid spend beyond the Claude Pro plan." |
| BLOCKING | "clean contract" load-bearing (5×) but never defined. | "clean contracts providing abstraction at every level" | FIXED — working definition added. |
| BLOCKING | "genuinely needed/justified" weasel; gates the central principle. | "Use inference only where it is genuinely needed" | FIXED — anchored to "if a function can do it, an LLM must not." |
| SIGNIFICANT | "reliability" undefined though it triggers guardrail relaxation. | "demonstrating reliability" | FIXED — dimension named (rate of validated-correct outputs per blast class). |
| SIGNIFICANT | "much better" lacks comparison axis vs independence. | "Do not build what others already do much better." | DEFERRED — left at requirements altitude. |
| SIGNIFICANT | "grunt work" undefined; offload thesis depends on it. | "absorb the grunt work onto local models" | FIXED — definition added. |
| SIGNIFICANT | Offload-ratio counting unit (task/step/token) unspecified. | "Share of tasks completed locally" | DEFERRED — diagnostic; unit to be set with targets. |
| SIGNIFICANT | Doc asserts authority over CLAUDE.md but leaves live conflict. | preamble "corrected, broader intent" | FIXED — see contradiction-finder / WORK-0015. |
| MINOR | time-to-done conflates two measures. | "Time to complete routine tasks / time-to-PR" | DEFERRED. |
| MINOR | "until the balance feels right" subjective. | "until the balance feels right" | FIXED — restated as testable capability. |
| MINOR | "realistic timeframe" unbounded. | "within a realistic timeframe and budget" | DEFERRED. |
| MINOR | "self-built capabilities" attribution rule undefined. | "capabilities or fixes that Lume itself produced" | DEFERRED — diagnostic. |

Deferred items consciously left unquantified: fuller specification crosses into
architecture, which acceptance criterion 3 forbids and scope-auditor confirmed.
