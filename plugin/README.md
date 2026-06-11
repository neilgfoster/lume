# lume

A deterministic, operator-driven iteration loop for getting real work done with
an AI agent - and keeping it honest. lume tracks **workstreams** (goals), breaks
them into **gated iterations**, and keeps every bit of state as inspectable JSON.

No LLM runs inside lume itself. It reads, validates, and writes on-disk state;
the thinking and the work happen in the iteration, never in the mechanism. Its
defining rule:

> **The machine does not act without the operator.**

Every iteration ends at a gate only a human passes - you accept or reject the
work. lume makes the loop legible (what's the objective, what phase am I in,
what's next) so neither you nor the agent loses the thread.

> Deciding whether to adopt lume? Read the honest limitations first — the
> [project README](../README.md) leads with **why you should not use it** (it's
> early, has one user, and its core value claim is unmeasured). This page is the
> guide for once you've decided to use it.

## Install

lume ships as a Claude Code plugin. The canonical install instructions live in
the [project README](../README.md#install); in short:

```
/plugin marketplace add neilgfoster/lume
/plugin install lume@lume
```

That puts the `lume` command on your PATH and loads the guiding skill that
teaches the agent how to drive the loop. For local development you can instead
run Claude Code with `claude --plugin-dir /path/to/lume/plugin`.

Requirements: `python3` on PATH. lume is **stdlib-only** - no runtime
dependencies, no daemon, no background process.

## First step

From the root of the repo you want to work in:

```
lume seed            # bootstrap: creates ./.lume/ and a seed workstream
```

`lume seed --new` captures a fresh project's why / scope / constraints /
done-when; `lume seed --existing` maps an existing repo. Seed is the only verb
that creates `.lume/` - every other verb expects it to exist.

## The iteration loop

```
lume status                 # orient: objective, current phase, Done / Now / Next
lume open "<title>"         # open the next iteration (refused unless the last is accepted)
   ... draft a crisp, binary Definition of Done ...
lume approve                # operator: the DoD is good, begin
lume start                  # work begins
   ... do the work, write an honest self-review ...
lume handback               # hand the work back for review
lume accept                 # operator: done   (or: lume reject "<reason>" -> lume redo)
```

An iteration moves through fixed phases - `proposed -> approved -> working ->
handback -> accepted` (or `rejected -> redo`) - and each move is a specific verb,
so an arbitrary phase can never be set. Lead a new area of work with a
`discovery` then a `planning` iteration (`lume open "<title>" -t discovery`)
before execution.

State lives in `.lume/` in your repo (workstreams, iterations, decisions, plans)
as JSON you can read and diff. It is your data, separate from the plugin.

## Machine-verifiable DoD

A Definition-of-Done item can carry an optional, machine-checkable `check`
alongside its prose, so the accept gate is a real check, not just an assertion.
Three predicate kinds:

- `{"kind": "command", "cmd": "python -m pytest -q"}` - passes iff the command
  exits 0 (run from the repo root);
- `{"kind": "file-exists", "path": "dist/app.tar.gz"}` - passes iff the path exists;
- `{"kind": "schema-valid", "entity": "objective", "path": "x.json"}` - passes iff
  the JSON validates against a lume entity schema.

`lume accept` evaluates the current iteration's checks first and **refuses** if
any fail (the iteration stays in `handback`). Items with no `check` are
prose-only and left to the operator's judgement. `lume check` runs the same
evaluation read-only (no transition) as a dry-run - exit 0 if nothing fails,
non-zero otherwise - and `lume status -w` shows how many items are
machine-verifiable. This is what lets an autonomous operator auto-accept only a
fully-verifiable, all-green DoD and escalate anything prose-only to a human.

Command checks run author-supplied shell, so treat a DoD's commands with the
same trust as running its test suite.

## Cross-repo capability gaps

A **gap** is a capability gap one repo records about lume - lume writes them
about itself, and adopters write them about lume. Gaps are the **demand
backlog**: problem statements from any source (adopters, the operator, a
`lume review`). Workstreams are the committed work that answers them; the two
stay separate entities, linked not merged. They live per-file under
`.lume/gaps/<source>-G<nnnn>-<stub>.json` (numeric id zero-padded in the filename for sequential sort, slugified title hint; the gap id itself stays `G<n>`), co-located with the rest of lume's state (a small schema: id, source, title, context,
status `open|acknowledged|resolved`, created, optional `workstreams` links and
a structured `resolution`).

- `lume gap add "<title>" [-c <context>]` records a gap in the current repo.
- `lume gap list` shows them.
- `lume gap scan` reads the repos in `ADOPTERS.json` (the source of truth;
  `ADOPTERS.md`'s table is generated from it), reaches each by `git`
  clone/fetch into a worktree, and ingests their **open** gaps into lume's own
  `.lume/gaps/` as `acknowledged` records. It is idempotent on `(source, id)` and
  skips an unreachable adopter rather than failing. Ingested gaps take their
  `source` from the `ADOPTERS.json` project name.
- `lume gap link <source> <id> -w <workstream>` records which workstream
  answers the gap (data, not prose); `lume status -w <workstream>` lists the
  gaps a workstream answers, derived by scan.
- `lume gap resolve <source> <id> [-w <workstream>] [-t <kind>] ["<note>"]`
  resolves a gap with a structured resolution (`kind`:
  `implemented|wont-fix|superseded|duplicate`, default `implemented`; the
  `-w` workstream is linked and recorded in the resolution). A re-scan won't
  revert it.

This is the lume↔adopter feedback channel. v0.1 delivers the **ingest** half;
signalling a resolution back to the adopter is a deliberate later step.

## Adversarial self-review

`lume review` keeps a repo true to its own charter via a repeatable self-review
whose output is shaped as queue-ready workstreams. The thinking is the agent's;
lume is deterministic plumbing on both ends (no LLM, no network, dates via the
clock seam):

- `lume review` (alias `lume review emit`) prints a review **protocol** seeded
  from the repo's charter: primarily lume's own state (every workstream's
  objective, decisions, plan, retro), plus a capped pattern scan for
  charter-like docs - or explicit files via repeatable `--charter <glob>`. With
  few or no docs it still emits and tells the agent coverage is thin. The
  protocol carries seven lenses (goal-fidelity, honesty, ecosystem fit,
  value/viability, keystone risk, vision coherence, and a META lens that turns
  the review on itself); the ecosystem lens instructs the agent to consult the
  **current** Claude Code features, plugin marketplace, and official best
  practices at review time - lume bakes in no such list.
- `lume review ingest <path>` validates the agent's filled-in result against
  the `review_result` schema, writes the human-readable report to
  `.lume/reviews/<date>-NN/findings.md` (NN = that day's sequence, from 01),
  persists the structured result through the store seam, and **prints - never
  runs -** the queue plan: `lume new`/`plan add` for proposed workstreams,
  `lume decide` for direction decisions, and `lume gap add` for the review's
  own self-improvement gaps (the META lens feeding the gap mechanic, so the
  review gets better over time). Adopting any of it stays behind the
  operator's gate.

## Hierarchical workstreams

A workstream can **spawn** child workstreams - a "sprint" that decomposes into
sub-work. `lume spawn <slug> "<title>"` creates a child of the `-w` target; the
child stores an optional `parent` (the parent's id) and children are discovered
by scan (no duplicated list).

- `lume status -w <parent>` lists the parent's children with each child's phase.
- `lume status` (the queue) indents a child row under a `(child of <parent>)`
  annotation within its review bucket.
- Closing a parent that still has **active** children is refused (close them
  first); reopening a child whose parent is closed is refused (reopen the parent
  first). Neither cascades - a parent's close never silently ends child work.

## Commands

lume is self-describing - `lume verbs` lists them all and `lume verbs <name>`
explains one; add `--json` to any verb for machine-readable output.

| verb | what it does |
| --- | --- |
| `status` | review queue (no `-w`), or one workstream's detail (`-w`) |
| `seed` | bootstrap `.lume/` + the seed workstream (your first step) |
| `new` | create a new workstream |
| `spawn` | create a child workstream of the `-w` target |
| `open` | open the next iteration |
| `approve` / `start` / `handback` / `accept` / `reject` / `redo` | move an iteration through its phases |
| `plan` | add or link a plan item |
| `decide` | log a decision |
| `retro` | create or refresh the retro artifact |
| `check` | dry-run the current iteration's DoD machine-checks (read-only) |
| `gap` | record / list / scan / link / resolve cross-repo capability gaps |
| `review` | emit the adversarial self-review protocol / ingest a review result |
| `snapshot` | print the derived Done / Now / Next snapshot |
| `get` / `schema` / `entities` | inspect state and its schemas as JSON |
| `close` / `reopen` | close or reopen a workstream |
| `migrate` | migrate legacy markdown workstreams to JSON |
| `verbs` | list every verb, or describe one |

## Layout

This is the installed plugin (the `plugin/` directory of the development repo —
only this ships to adopters):

```
bin/lume               # the executable (on PATH when installed as a plugin)
src/lume/              # the engine (stdlib-only Python package)
skills/lume/           # the guiding skill Claude Code loads
.claude-plugin/        # plugin.json
README.md              # this guide
```

See [src/lume/README.md](src/lume/README.md) for engine internals, and the
[project README](../README.md) for the development repo, honest limitations, and
[ADOPTERS](../ADOPTERS.md).
