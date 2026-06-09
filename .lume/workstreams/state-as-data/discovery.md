# state-as-data - discovery

Maps the state lume carries in markdown today, drafts a JSON state model and a
discovery/validation seam, and lists the forks for planning. No engine code.

## 1. State inventory (what's in markdown, who reads/writes it)

Today every file is markdown; the engine treats *some* fields as state and the
rest as prose. The split below is the whole point of this workstream.

### objective.md (one per workstream)
- **frontmatter** `status: active|closed` - machine state. Read `Workstream.status`
  / `is_closed`; written `Repository.create_workstream`, `Workstream.set_status`.
- **body** `# <title>` + objective prose - human artifact. `objective_line()` just
  grabs the first non-empty body line for display. Absent frontmatter reads as
  active (the migration mechanic in `set_status`).

### iterations/NNN.md (one per iteration)
- **frontmatter** - all machine state, via `Iteration.from_text`/`to_text`:
  - `id` (zero-padded int), `type` ({discovery,planning,execution,closeout};
    legacy default `build`), `phase` (proposed|approved|working|handback|
    accepted|rejected), `opened` (ISO date).
- **body** - mostly prose artifact, two machine reads:
  - `# Iteration NNN - <title>` -> `Iteration.title` (parsed).
  - `## Verdict` section accumulates `DATE | ACCEPTED|REJECTED | reason` lines;
    `accepted_on()` parses the last ACCEPTED date. **This is state encoded as
    prose** - written by `Workstream.transition` for accept/reject.
  - `## DoD` (checkbox list), `## Self-review`, `## Handback` - free-form,
    inference-authored. Never parsed by the engine.

### snapshot.md (one per workstream) - ALREADY a derived view
Built by `snapshot.build_snapshot` from iteration + plan state. Owns title,
`Updated:` stamp, `## Done` (accepted iterations), `## Now` (latest iteration).
`## Next` is derived from plan.md when present, else a hand-authored tail is
preserved verbatim. Idempotent. This file is the proof-of-concept that the
view-from-state pattern already works here.

### plan.md (optional, one per workstream)
- **`## Items`** lines `- P<n> | type | iter:<NNN|-> | committed|optional | sketch`,
  parsed by `parse_plan` into `PlanItem(id, type, iter, tag, sketch)`. Machine
  state. Everything else (header, schema doc, sequencing rationale, deferred)
  is prose the parser ignores.

### decisions.md / retro.md - pure prose
Append-only human/agent log (`- DATE | (context) label | rationale`). The engine
**never** parses these. Pure artifacts.

### Implicit state (not in any file)
- Workstream **slug** = directory name. **Membership/order** of iterations =
  `glob("*.md")` sorted by numeric stem. **Active set / queue** = derived by
  scanning every workstream's status + current iteration phase (`cli._render_queue`).

**Conclusion:** the authoritative machine state is small and already isolated -
status, the iteration frontmatter quad, verdict outcomes, and plan-item lines.
Everything else is prose artifacts or already-derived views. "State is data" is
mostly *extraction*, not invention.

## 2. Candidate JSON entity model

Three entities; prose stays in markdown artifacts that state *points at*.

```json
// workstream
{ "slug": "state-as-data", "title": "State is Data",
  "status": "active",                     // active | closed
  "objective_artifact": "objective.md" }  // prose lives here

// iteration
{ "id": 1, "type": "discovery", "phase": "working",
  "opened": "2026-06-09", "title": "Map current markdown state ...",
  "verdicts": [ { "date": "2026-06-09", "verdict": "accepted", "reason": null } ],
  "dod_artifact": "iterations/001.md" }   // DoD/self-review/handback prose

// plan_item
{ "id": "P1", "type": "execution", "iter": 4,   // null until opened
  "tag": "committed", "sketch": "..." }
```

Relationships: workstream 1-* iterations (ordered by id); plan_item 0..1 ->
iteration (`iter`). Derived, not stored: `done` = linked iteration accepted;
`now` = latest iteration; `next` = first not-done plan item; the queue. These
stay derived (matches lifecycle decision (a): derive workstream phase, don't
store it).

## 3. Validation approach

- **Format:** JSON Schema (draft 2020-12) - one schema per entity, themselves
  shipped as data under the engine.
- **Where:** at the persistence boundary (`Repository`/model load+save). Every
  read validates on load; every write validates before persisting. Invalid state
  is a named error at the boundary, never silently surfaced downstream. This is
  the deterministic-over-inference non-negotiable applied to state shape.
- **Dependency cost (fork for planning):** the engine is deliberately
  dependency-free (`frontmatter.py` reimplements YAML rather than import one).
  The shapes here are flat enums/strings/ints - a ~40-line stdlib-only validator
  covers them, vs adding `jsonschema`. Constitution leans toward the vendored
  validator; flagged in §6(b).

## 4. Discovery seam (how an agent orients cold)

New read-only verbs, all emitting machine-parseable JSON:
- `lume entities` - list the entity kinds the engine knows (workstream,
  iteration, plan_item).
- `lume schema <entity>` - print that entity's JSON Schema.
- `lume get -w <slug> [<entity> [<id>]]` - emit current state as JSON
  (whole workstream, or a kind, or one instance).

With these an agent dropped into an unknown repo runs `entities` -> `schema` ->
`get` and fully understands the format without reading source or guessing
conventions. Mutation stays through the existing verbs (open/transition/...),
which become "validate -> write JSON -> regenerate views"; no hand-editing.

## 5. Markdown-as-view boundary

- **Authoritative state (JSON, sole writer = tooling):** status; the iteration
  quad (id/type/phase/opened) + title + verdict outcomes; plan items.
- **Prose artifacts (markdown, authored by human/agent, *pointed at* by state):**
  objective body, DoD text, self-review, handback notes, verdict *reasons*,
  decisions.md, retro.md, plan rationale.
- **Derived views (markdown, regenerated, never hand-edited):** snapshot.md
  today; optionally a rendered per-iteration/per-workstream view. Regeneration
  runs on every mutation (as `record_snapshot` does now) - or on demand via a
  `render` verb (fork §6(e)).

The line: a field the engine *branches on* is JSON; text only a human/agent
reads is a markdown artifact; anything shown for orientation is a regenerated
view.

## 6. Open forks (resolve in planning)

- **(a) Granularity** - one `state.json` per workstream, vs per-iteration JSON
  files, vs a single repo-wide store. Git diffability + the per-iteration write
  pattern lean toward per-workstream or per-iteration files, not one big store.
- **(b) Validation dependency** - vendored stdlib validator vs `jsonschema` lib
  (see §3). Constitution leans vendored.
- **(c) Migration** - the two closed workstreams + this one are markdown. One-
  shot converter for all, or new-workstreams-only? The dogfooding done-when
  requires *this* workstream to end up tracked in JSON, so at minimum a converter
  for the active one.
- **(d) How much prose becomes data** - are DoD checkbox items state (their
  checked/unchecked drives the self-review gate) or artifact? Leaning artifact
  for v1, but flagged.
- **(e) View regeneration** - on every mutation (like snapshot now) vs on-demand
  `render` verb.
- **(f) Contract fit** - JSON state must sit *behind* the existing Repository
  contract (the documented future GitHub/Jira swap seam), not bypass it.

## 7. Scope held / deferrals

- No engine code written this iteration (discovery only).
- **Deferred to planning:** resolve forks (a)-(f); sequence the slices; decide
  migration order.
- **Deferred to execution:** implement `entities`/`schema`/`get` verbs; JSON
  read/write with boundary validation; rewire mutating verbs to write JSON +
  regenerate views; migrate this workstream's state to JSON (dogfood).
