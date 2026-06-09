# Lume — Open Questions, Assumptions & Risks

## Load-bearing assumptions to validate
1. **Honest self-review against the DoD works.** The whole loop assumes Claude can adversarially self-judge against a DoD and only hand back work that genuinely meets it. If it self-certifies a soft DoD as "done," the operator returns to junk and wastes scarce time. *Validation: run real iterations and measure reject rate at the human gate; track how often "Claude said done" survives operator review.*
2. **A DoD can be made crisp enough to self-check in ~15 min of work.** Vague DoDs make both self-review and human review unreliable. *Validation: inspect whether DoDs written in practice are checkable, not aspirational.*
3. **Done/Now/Next is enough to re-orient in ~2 min after a multi-day gap** without re-reading everything. *Validation: time real re-orientation; note when you had to dig deeper.*
4. **Ceremony pays for itself.** Defining + approving a DoD per 15-min iteration saves more time than it costs. *Validation: notice when you route around Lume and use raw Claude Code instead.*
5. **The contract seams are in the right place** — each expresses both members of its example pair cleanly (files + GitHub Issues; single reviewer + panel; iterate-refine + discover-dispose). *Validation: try to express the second member on paper before building.*

## Risks (rough severity)
| Risk | Severity | Notes |
|---|---|---|
| Ceremony exceeds value; operator abandons Lume for raw Claude Code | **High** | The headline failure mode. Mitigation: keep gates minimal, cut anything that doesn't buy back time. |
| Claude self-certifies a soft DoD; operator returns to junk and loses trust in the loop | **High** | The second-most-feared mode. Mitigation: crisp DoDs, adversarial reviewer separate from worker, measure survival rate. |
| Scope creep — Lume grows into something it was never meant to be | **Medium-High** | Mitigation: stay-true-to-intent non-negotiable; native-feature audit; future adversarial review of operator decisions. |
| Contracts abstracted from a single implementation leak when the second arrives | **Medium** | Mitigation: the two-implementations design test; don't fully abstract until pulled. |
| Approval overload: arbitrary depth + approve-at-every-level + time-poor | **Medium** | Tolerable in v1 (short iterations, async rounds) *only if orientation is good*; revisit with earned delegation. |
| Framework turns into bureaucracy as nesting deepens | **Medium** | Directly tied to ceremony risk; the flat review queue is the main defence. |
| Building contracts/configurability upfront delays the bootstrap | **Medium** | Decision taken to include contracts in v1; risk is over-engineering before the loop has run once. |
| Orientation fails at depth — Done/Now/Next insufficient three levels deep | **Medium** | Breadcrumbs up the tree may be needed; unproven. |

## Open questions / known unknowns
- **Adversarial review of operator decisions:** what triggers it (every decision? scope-affecting ones only?), what rubric defines "true to intent," and how it avoids becoming ceremony itself. Directional guardrail; mechanism unknown.
- **Detached-mode keying:** when state lives outside the target repo, how is it keyed and located (by repo path under home, under Claude's project dir)? Technical spike — deferred with detached mode.
- **Deterministic vs inference boundary:** the exact line — control flow/state/gates deterministic, work inferential — needs to be made concrete in the implementation, not just stated.
- **What "self-review" mechanically is:** subagent with the DoD as rubric, separate from the worker? Single vs panel in v1? Open.
- **Kill/pivot criteria beyond abandonment:** is there an explicit trigger to pivot the design, or only the implicit "I stopped opening it"?
- **Time budget in numbers:** no hard figure for available time or any deadline; "lightweight" currently calibrated only against ≈15–25 min dip-ins.
- **Why now (explicit):** the trigger to build this *now* vs continue coping is implicit (accumulated context-loss pain); not sharply stated.
- **Multi-operator specifics (when promoted):** operator identity in the decision log, concurrency when two operators touch one workstream, whether reputation becomes per-operator as well as per-Claude.
- **Self-improvement mechanism:** what usage signal Lume would capture (friction points, reject reasons, ceremony cost) to later improve itself.
