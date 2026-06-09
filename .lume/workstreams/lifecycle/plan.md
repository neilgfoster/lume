# lifecycle - plan (living)

The forward source of truth for this workstream. Edited as we learn (each change
logged in decisions.md with its why). Once P3 ships, the snapshot's `## Next` and
a "step N of M" line are *derived* from this file; until then they are kept by
hand.

## Schema (parseable later, per decision e)

One plan item per line, stable format:

    - P<n> | <type> | iter:<NNN|-> | <committed|optional> | <one-line DoD sketch>

- **P<n>** plan-item id (distinct from iteration ids; a P-item becomes an
  iteration when opened, linked via `iter:`).
- **type** one of the template's type vocabulary (default {discovery, planning,
  execution, closeout}).
- **iter:** the iteration id fulfilling this item once opened, else `-`.
- **committed | optional** the constitutional tag (decision: is this iteration
  justified, or cuttable).
- **DoD sketch** the intended done-when in one line; refined into the full DoD
  when the iteration is opened.

Derived (decision e), 1 plan item <-> at most 1 iteration (if reality diverges,
amend the plan + log why):
- **done** = the item's `iter:` exists and that iteration is `accepted`.
- **next** = the first item that is not done.
- **position** = "step (index of next) of (count)".

## Items

- P1 | execution | iter:004 | committed | Queue + multi-workstream rework: retire `.lume/current`; in-progress = all `status:active`; commands take `-w <slug>` (default to the sole active, error listing actives when omitted with >1); `lume status` becomes the cross-workstream queue (AWAITING YOU = handback iterations across active; IN PROGRESS = other active; CLOSED listed); `new`/`close` no longer touch a cursor; single-active flows still work via the default; tests green. Reworks 001.
- P2 | execution | iter:005 | committed | Un-hardcode `type` in `lume open`: `open` takes a type from the (template-default {discovery,planning,execution,closeout}) vocabulary, default `execution`, validates (rejects unknown), persists `type:<t>`, and surfaces it in status/queue; tests green.
- P3 | execution | iter:006 | committed | Derive Next + plan-position from this living plan: engine parses plan.md (this schema), derives the snapshot `## Next` and a "step N of M -> next: P<k>" line from the first not-done item (done = linked iteration accepted); `## Next` stops being hand-authored; malformed/empty plan handled gracefully; tests green. (Depends on P1's status surface.)
- P4 | execution | iter:007 | committed | Per-type DoD-skeletons (decision d): opening an iteration of each type pre-loads a type-specific DoD/body skeleton (discovery: questions+artifact; planning: decisions+plan+sketches; execution: today's build template; closeout: retro); skeletons are data; tests green. (Depends on P2.)
- P6 | closeout | iter:008 | committed | Close-out / retro: did typed/phased practice + the queue + the derived plan buy back more time than they cost? Assess against the objective's done-when (typed/phased iterations; tooling tracks active vs closed + multiple in-progress; this workstream run through the lifecycle); log decisions; `lume close` the workstream. (Prototype: build-lume's retro.)

## Sequencing rationale (constitutional, decision c = order is convention)

- P1 first: foundational orientation + corrects 001; needed to honestly run >1
  workstream (and we are about to want a second one to test the queue against).
- P2 next: tiny, the named seam from the handoff; unblocks all typed work;
  sequenced after P1 so `lume open`'s arg parsing is reworked once, not twice.
- P3: ends the hand-maintained-`Next` drift observed this session; depends on
  P1's status surface + this schema.
- P4: the typed-iteration payoff (pre-loaded DoDs); depends on P2.
- P6: close-out (P5 was cut here - see Deferred).

## Deferred (not committed; revisit only if a named puller appears)

- (was P5) Practice-template-as-data + populate two templates + live contract
  proof. CUT at the planned optional point (operator call, 2026-06-09): the
  objective's done-when is met without it, and the constitution favours the cut
  over the largest item; the contract proof can move to ordinary future use (it
  passed on paper in discovery.md §4). Revisit when a second real template is
  actually needed.
- Stored workstream-level phase machine + phase-transition gate (option A) -
  only if orientation needs more than the snapshot/queue give (decision a).
- Decomposition / nesting; detached/invisible mode; multi-agent review panels -
  out of this workstream per scope.md priority sequence.