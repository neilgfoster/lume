# build-lume - retro (iteration 006)

Review of iterations 001-005: did the loop buy back more time than its ceremony cost?

## Operator verdict (the load-bearing input)
**Net positive.** The operator's lived experience across 001-005 is that the loop
saved more than it cost. This is the data point that matters most for the
constitutional question, and it is not my inference - it is the operator's call,
captured at this iteration.

## Per-step verdict (scope.md steps 1-5)
| Step | Cost | Saves | Net |
|---|---|---|---|
| 1. Create workstream (objective) | One small file. | Anchors every iteration to a stable "why"; the snapshot derives Done from it. | **Positive** (barely exercised - one workstream). |
| 2. Propose + approve DoD | Writing + reading a DoD each iteration. | The workhorse. Caught both bad iterations (002, 003) before they shipped; kept scope tight; made self-review checkable. | **Positive** - the highest-value gate. |
| 3. Work + adversarial self-review | Claude's time, not the operator's. | Handbacks arrived evidence-backed (each DoD item + proof), so operator review was fast. | **Positive**. |
| 4. Handback + Done/Now/Next, no auto-commit | Writing the handback + snapshot. | Operator rebuilds context from a tight summary; no surprise commits. Auto-snapshot (004/005) removed the snapshot cost entirely. | **Positive** - cost actively driven down. |
| 5. Accept / reject | One command. | The consent gate; the two rejects landed here. Cheapest step, high leverage. | **Positive**. |

No step is a candidate for cutting. The one cost that was real (manually keeping
the snapshot current) was engineered away in 004-005.

## Load-bearing assumptions (questions.md) vs evidence
1. **Honest self-review against the DoD works** - **HELD (with a caveat).** Self-review
   never falsely passed a DoD item; every handback's claims checked out at the human
   gate. The two rejects (002, 003) were *not* Claude self-certifying soft DoDs - they
   were requirements the DoD never encoded (002: engineering structure/location/tests;
   003: accept-needs-no-reason). So self-review is honest *within the DoD's scope*. The
   lever is DoD completeness, not self-review dishonesty.
2. **A DoD can be crisp enough to self-check** - **HELD.** Every DoD from 001 on was
   binary and evidence-backed; nothing aspirational survived. Refinement: crisp is
   necessary but not sufficient - see the rejects. A DoD must also be *complete*
   (encode what would make the work rejectable). New practice: when proposing a DoD,
   ask "what could get this rejected that the DoD doesn't capture?"
3. **Done/Now/Next re-orients in ~2 min after a multi-day gap** - **UNPROVEN.** Every
   iteration this session was same-day; no real multi-day gap elapsed, so the headline
   re-orientation claim was never actually tested. The snapshot was useful as a running
   summary, but the gap-recovery case is still open. Honest gap to validate later.
4. **Ceremony pays for itself** - **HELD** (operator verdict: net positive), with the
   caveat that it's one operator, one workstream, six iterations - a strong signal, not
   a measurement.
5. **The contract seams are in the right place** - **PARTIALLY UNPROVEN.** Only the
   persistence/tracking seam (`repository.py`) was built. The review and practice seams
   were never implemented, so the "express both members of the example pair" design test
   was not run for them. The next workstream exercises the practice seam directly.

## Overall verdict
**Net positive, with two honest caveats.** The loop buys back time (operator-confirmed),
caught two bad iterations it was designed to catch, and drove its own residual ceremony
cost to near zero. Unvalidated: (a) re-orientation across a real multi-day gap; (b) two
of the three contract seams. Neither is a reason to stop; both are things the next
workstream and ordinary future use will test.

## Close-out
**build-lume is CLOSED.** Objective "Done-when: Lume's own linear loop (scope.md 1-5)
runs on a single flat workstream, and is used to advance build Lume itself" is **MET**:
steps 1-5 are deterministic tooling and ran build-lume through iteration 005 - including
a full reject -> redo -> accept cycle (003) - entirely on Lume's own verbs.

## Handoff to the next workstream
**Refine the workstream process into an explicit lifecycle (practice contract).** A
workstream should run as phased practice rather than a flat iteration list:
- **Discovery** - build context.
- **Planning** - plan the phases required to achieve the objective.
- **Execution** - iterations run to completion.
- **Close-out** - a final wrap iteration (this retro is the prototype).

This formalises what build-lume did ad hoc and pulls on the so-far-unproven practice
seam. Concrete first gap to fix there: `lume open` hardcodes `type: build`; typed/phased
iterations are the practice contract made real.
