# lifecycle - retro (iteration 008)

Close-out of the lifecycle workstream: did running work as explicit phased
practice (discovery -> planning -> execution -> close-out), with typed iterations
and a living plan, buy back more time than its ceremony cost?

## Per-stage verdict (as actually run, 002-008)
| Stage | Iterations | Cost | Saved | Net |
|---|---|---|---|---|
| Discovery | 002 | One analysis iteration, no code. | Grounded the four stages in build-lume's real history; surfaced the representation fork (per-iteration `type`) and the per-template-vocabulary leak *before* any code. Planning aimed correctly because of it. | **Positive** |
| Planning | 003 | One iteration + standing up plan.md/decisions.md. | Every later execution iteration opened with a ready DoD sketch + committed/optional tag. Absorbed two mid-stream operator redirections (plan-tracking; multi-workstream) as logged plan changes instead of derailment. | **Positive** - the highest-leverage stage. |
| Execution | 004-007 | Four build iterations. | The queue + derived-Next killed a real, recurring cost (see below). Typed iterations + per-type DoD skeletons: modest but real. | **Positive** |
| Close-out | 008 | This iteration. | Forces the honest done-when assessment + carry-forward; closes the workstream on the tooling. | **Positive** |

## The standout win (lived evidence)
Until P3 (006), I hand-edited the snapshot's `## Next` after *every* accept, and
it drifted every time. P3 made `## Next` **derived** from the living plan.md;
after that, accepting an iteration auto-advanced "step N of M -> next" with zero
hand-editing, and **cutting P5 mid-stream flowed through the derivation with no
code change at all**. This is build-lume's 004 pattern (derive Done/Now, stop
maintaining it) repeating for the forward view - the clearest case of ceremony
paying for itself this workstream.

## Objective done-when, clause by clause
| Clause | Verdict | Evidence |
|---|---|---|
| Typed/phased iterations (not a flat list) | **MET** | `lume open --type` with a validated vocabulary + per-type DoD skeletons (005, 007). The workstream itself ran discovery(002) -> planning(003) -> execution(004-007) -> closeout(008). (001-005 frontmatter is legacy `type: build`, opened before the feature; 006+ are typed.) |
| Tooling tracks active vs closed; >1 workstream can coexist | **MET (with caveat)** | `status: active|closed` field (001); the resolver + queue handle N active workstreams (004). Caveat: only ever one *live* active workstream existed, so multi-workstream is proven by tests, not by use. |
| "...and which one is current" | **MET, but EVOLVED** | The objective's single-"current" wording was superseded in 004 (decision f): the global mutable cursor was retired for a cross-workstream **queue + `-w` target** (sole-active default). Honest evolution, not the literal original wording. |
| This workstream run through the lifecycle to prove it | **MET** | All eight iterations ran on the engine's own verbs; the practice was dogfooded end to end, including a mid-stream plan cut. |

## Load-bearing assumptions (questions.md) vs evidence
1. **Honest self-review** - HELD, lightly tested. No DoD item self-certified falsely. Notable: **zero rejects** this workstream (vs build-lume's two). The "what could get this rejected?" completeness check at proposal time plausibly pre-empted them - but zero rejects also means the human gate's catch-rate went untested this round.
2. **DoD crisp enough to self-check** - HELD. DoDs stayed binary/evidence-backed; planning even produced binary DoD *sketches*.
3. **Done/Now/Next re-orients in ~2 min after a multi-day gap** - STILL UNPROVEN (all same-day, as in build-lume). Mitigated: `## Next` is now derived, so it cannot silently drift stale.
4. **Ceremony pays for itself** - HELD within this workstream (operator drove the loop repeatedly; the derived-Next win is concrete). Caveat: two workstreams, one author, one day - a strong signal, not a measurement.
5. **Contract seams in the right place** - persistence seam exercised harder (multi-workstream selection/queue). **Practice seam: partially proven** - the lifecycle ran as typed/phased iterations and the templates-as-data *shape* exists (TYPES, per-type skeletons), but the live two-template contract proof was **cut (P5)**; it passed only on paper (discovery §4). Review seam: still unbuilt.

## Overall verdict
**Net positive.** The phased practice formalised what build-lume did ad hoc, and
the derived plan turned the operator's two mid-stream redirections into cheap,
logged plan edits rather than rework. The clearest payoff (derived Next) removed
a cost I was visibly paying every iteration. Honest caveats: the typed-iteration
machinery and the queue are lightly exercised (one closeout/planning/discovery
iteration each; one live workstream), and the practice contract is proven in
shape but not in a second live template.

## Close-out
**lifecycle is being CLOSED.** Objective met (see the table; "current" evolved to
the queue). Closed via `lume close` as the post-acceptance final act.

## Carry-forward (also in decisions.md)
- **P5 contract proof** (templates-as-data + two live templates) - cut; revisit when a second real template is needed.
- **`lume use`** to switch among multiple *active* workstreams - deferred; no second active workstream ever existed to pull on it.
- **Auto-writeback of plan `iter:` links** - they were maintained by hand this workstream.
- **Queue multi-workstream behaviour** - only ever lived with one active workstream; spin up a real second one to exercise it.
- **Re-orientation across a real multi-day gap** - still unproven (carried from build-lume).
- **Review contract seam** - still unbuilt.
- **Queue "awaiting you"** surfaces only `handback`; an `accepted` (ready-to-open-next) state is not surfaced - candidate refinement.
