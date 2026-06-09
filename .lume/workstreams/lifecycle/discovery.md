# Discovery - shape of the explicit lifecycle

Context for designing typed/phased practice. No engine code here; this aims
to make planning (003) cheap and well-aimed. Decisions are planning's to make.

## 1. The stages are real - mapped onto build-lume's actual history

build-lume already ran all four stages. The key finding: **only execution and
close-out happened *inside* the iteration loop; discovery and planning happened
*outside* it**, up front, in `docs/`. The lifecycle feature's job is to bring
discovery and planning *inside* the loop as first-class iteration stages.

| Stage | Where build-lume did it | Artifact (cited) |
|---|---|---|
| Discovery | Before the loop, ad hoc | `docs/vision.md` (why/users/core model); `docs/questions.md` (load-bearing assumptions, risks, unknowns) |
| Planning | Before the loop, ad hoc | `docs/scope.md` (v1 spine, "rough priority sequence", "first slice of work"); `docs/constraints.md` decision log |
| Execution | Inside the loop, iterations 001-005 | 001 Runnable orientation; 002 Engine as a tested module (incl. a reject->redo); 003 Gate-transition commands (incl. a reject->redo); 004 Derive Done/Now; 005 Fold snapshot refresh into the verbs |
| Close-out | Inside the loop, iteration 006 | `retro.md`: per-step verdict, assumptions-vs-evidence, handoff |

Two corollaries that shape the design:
- **Discovery/planning are not one-shot.** Vague scope fractals (vision.md:
  "large problems fractal into workstreams"). A workstream may re-enter
  discovery mid-stream. So stages are not a strict once-through pipeline; they
  recur.
- **Close-out is already prototyped** (retro.md / iteration 006). Execution is
  already the engine's only real type today (`type: build`). Discovery and
  planning are the genuinely missing stages.

## 2. Core design fork (planning to ratify)

How is "the lifecycle" represented?

- **A - workstream-level phase machine.** The workstream carries
  `phase: discovery|planning|execution|closeout`; iterations are constrained by
  it; phase->phase transitions are gated.
  - *Gives:* an explicit "where are we" at the workstream level; enforced
    progression.
  - *Costs:* a second state machine alongside the iteration phase machine, plus
    a new transition gate = real ceremony. Rigid: a discovery spike during
    execution forces phase thrash.

- **B - per-iteration type (recommended).** Each iteration carries
  `type: discovery|planning|execution|closeout|...`; `lume open` takes the type
  instead of hardcoding `build`. The "lifecycle" is the *sequence* of typed
  iterations; no separate workstream phase is stored.
  - *Gives:* the smallest change that kills the `type: build` hardcode (the seam
    the handoff named); no second state machine; the step-sequence becomes data
    (scope.md: "express the iteration step-sequence as data so templates are a
    later population of an existing shape, not a rewrite").
  - *Costs:* no *enforced* progression - ordering is convention carried by the
    operator's consent gate, not a phase gate. No stored workstream-level
    "where are we" (but it is derivable - see below).

- **C - both.** Workstream phase + iteration type, with a legality rule binding
  them. Most expressive, most ceremony; premature.

**Recommendation: B.** It is the minimal honest step, adds no ceremony the
constitution would question, and turns practice templates into data. The
workstream-level "where are we" can be *derived* (the type of the latest/active
iteration, or position in the template sequence) rather than stored - echoing
004's move of deriving Done/Now instead of hand-maintaining them. Adopt A's
stored phase + gate later *only if* orientation proves to need more than the
Done/Now/Next snapshot already gives. Defer A until something pulls on it.

## 3. Minimal data shape (for option B)

- **Iteration `type` becomes meaningful.** The field already exists
  (`type: build`). Widen its vocabulary to the stage set and have `lume open`
  set it (default `execution`) instead of hardcoding `build`. Validate against
  an allowed set.
- **A practice template = an ordered list of iteration types, as data/config.**
  e.g. `delivery = [discovery, planning, execution*, closeout]` (execution
  repeats). This is scope.md's "step-sequence expressed as data"; templates are
  later *population* of this shape, not new code.
- **Per-type defaults = data.** Each type carries a default DoD-skeleton / body
  template (discovery: "questions answered + artifact"; planning: "phases &
  their DoDs named"; execution: today's build template; closeout: retro
  template). This is what makes a typed iteration *buy back time* - it
  pre-loads the right DoD shape.
- **Workstream "phase" is derived, not stored** (the active iteration's type /
  template position).

**Smallest first execution slice (what 004 builds):** make `lume open` accept a
`type` from the stage vocabulary (default `execution`), persist it in
frontmatter, validate it, and surface it in `lume status`. That is it - no
templates, no per-type DoD skeletons, no ordering enforcement, no workstream
phase. Un-hardcode `type` and nothing more. Templates and DoD-skeletons are
later, independently valuable slices.

## 4. Practice-contract design test (on paper)

scope.md requires the practice seam to express *both* members of its example
pair cleanly; the retro flagged this as still unproven. Under shape B both are
just ordered type-lists over the *same* typed-iteration shape - no bespoke code
per template:

- **delivery (iterate -> refine -> iterate):** `[execution, execution, ...]`
  repeating. "refine" is not a new mechanism - it is the existing
  reject->redo / accept-next loop already in the engine. Template =
  `[discovery?, execution*, closeout]`.
- **research (discover -> research -> build -> dispose):**
  `[discovery, research, execution(build), closeout(dispose)]`.

Both reduce to: "an ordered list of iteration types + a per-type DoD-skeleton,"
read by one engine path.

**Leak to record:** `research` and `dispose` are stage types *beyond* the four
lifecycle stages. So the type vocabulary must be a property of the **template**
(open/configurable), not a fixed four-value enum baked into the engine. The
four lifecycle stages are the *default* (delivery-style) set; a template may
declare its own. Planning must decide this - it is the one thing that, if
hardcoded now, would make the contract leak when the second template arrives.

## 5. Scope held, deferred work, ceremony cost

**No engine code in this iteration.** Discovery produced only this artifact;
the loop's behaviour is unchanged (git: only `discovery.md` + this iteration's
file + the auto-refreshed snapshot).

**Deferred to planning (003):** ratify the fork (B vs A/C); fix the type
vocabulary and the default template; decide whether ordering is enforced or
convention; decide the per-type DoD-skeletons; decide that the type set is
per-template (the item-4 leak).

**Deferred to execution (004+):** 004 = un-hardcode `type` in `lume open`
(smallest slice). Then per-type DoD templates. Then practice-template-as-data +
populate the two example templates. Workstream-phase machine (option A) only if
orientation demands it.

**Ceremony-cost check (constitutional):**
- Per-iteration `type` (option B): ~zero cost (a field that already exists + a
  flag on `open`). Clears its bar trivially.
- Per-type DoD-skeletons / templates: must each buy back time by pre-loading the
  correct DoD shape; flag for measurement when built, cut any that do not.
- A stored workstream-phase machine + transition gate (option A): **real**
  added ceremony (a consent/gate per phase). Adopt only if it buys orientation
  the Done/Now/Next snapshot cannot. Not now.
