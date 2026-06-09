# state-as-data - plan (living)

The forward source of truth for this workstream. Edited as we learn (each change
logged in decisions.md with its why). The snapshot's `## Next` and "step N of M"
are derived from this file.

## Schema (parseable)

One plan item per line, stable format:

    - P<n> | <type> | iter:<NNN|-> | <committed|optional> | <one-line DoD sketch>

- **P<n>** plan-item id (distinct from iteration ids; becomes an iteration when
  opened, linked via `iter:`).
- **type** one of {discovery, planning, execution, closeout}.
- **iter:** the iteration id fulfilling this item once opened, else `-`.
- **committed | optional** is this iteration justified, or cuttable.
- **DoD sketch** the intended done-when in one line; refined into the full DoD
  when the iteration is opened.

Derived: done = the item's `iter:` exists and that iteration is accepted; next =
first not-done item; position = step (index of next) of (count).

## Items

- P1 | execution | iter:003 | committed | Schemas + validator: author workstream/iteration/plan_item JSON Schemas (draft-2020-12 subset) as engine data; vendored stdlib validator raising a named boundary error on mismatch; unit tests cover each schema valid + invalid. No wiring yet.
- P2 | execution | iter:004 | committed | state.json model behind the Repository seam: a state module that loads+validates and saves+validates a per-workstream state.json (workstream record + iterations + plan items); Repository owns load/save/validate; pure and tested. No verb rewiring yet.
- P3 | execution | iter:005 | committed | Migration converter: read each workstream's existing markdown (objective/iteration frontmatter + verdict lines + plan-item lines) and emit state.json; idempotent; round-trips the two closed workstreams; this workstream migrated to JSON (dogfood). Prose artifacts left in place.
- P4 | execution | iter:006 | committed | Data-first model bridge (behaviour-preserving, was "P4a"): Iteration gains to_entity/from_entity + a canonical verdict parser shared with migrate; accepted_on routes through it; no verb/Repository change; all existing tests stay green. Prepares the flip.
- P5 | execution | iter:- | committed | Flip the source of truth (was "P4b"): Workstream loads/saves state.json (via Repository) as the truth for status + iterations; open/transition/close/set_status mutate validated state then regenerate views (snapshot.md, iteration frontmatter, objective status); plan.md stays authored + mirrored into state.plan; no machine field read from markdown (grep-verified); tests updated to the state-backed model.
- P6 | execution | iter:- | committed | Discovery verbs: `lume entities` lists entity kinds; `lume schema <entity>` prints its JSON Schema; `lume get [-w <slug>] [<entity> [<id>]]` emits current state as JSON. All read-only, machine-parseable, tested.
- P7 | closeout | iter:- | committed | Retro + close: did JSON-backed state buy back more time than its ceremony? Assess the objective's done-when (state is schema-validated JSON; CLI is sole mutator + exposes discovery/schema verbs; markdown regenerated not authored; this workstream tracked under JSON). Log decisions; lume close.

## Sequencing rationale

- P1 first: the schema + validator are the contract everything else writes
  against; nothing can be validated before they exist.
- P2 next: state I/O depends on P1's schemas; isolated behind Repository so the
  verb rewire (P4) is a swap, not a rewrite.
- P3 before P4/P5: migration produces the state.json files the rewired verbs
  need, and converts the dogfood workstream up front so the flip runs against
  real JSON.
- P4 then P5 (the old monolithic "P4", split): P4 is the behaviour-preserving
  model bridge; P5 is the atomic source-of-truth flip that consumes it. Split so
  each lands as a small, reviewable diff. P-ids are numeric (the plan parser only
  matches P<digits>), so the split is P4/P5, not P4a/P4b.
- P6 after P5: discovery verbs are read-only over the finished shape; sequencing
  them last avoids reworking them as the shape settles.
- P7: close-out / retro against the done-when.

## Deferred (not committed; revisit only if a named puller appears)

- Standalone `lume render` verb (fork e) - auto-regen covers the value; add only
  if on-demand rendering is actually needed.
- DoD checkboxes as schema'd data (fork d) - only if a gate needs machine-
  checkable DoD completion.
- Swap the vendored validator for `jsonschema` (fork b) - only if shapes grow
  beyond flat scalars/enums/arrays.
