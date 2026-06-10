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

## Commands

lume is self-describing - `lume verbs` lists them all and `lume verbs <name>`
explains one; add `--json` to any verb for machine-readable output.

| verb | what it does |
| --- | --- |
| `status` | review queue (no `-w`), or one workstream's detail (`-w`) |
| `seed` | bootstrap `.lume/` + the seed workstream (your first step) |
| `new` | create a new workstream |
| `open` | open the next iteration |
| `approve` / `start` / `handback` / `accept` / `reject` / `redo` | move an iteration through its phases |
| `plan` | add or link a plan item |
| `decide` | log a decision |
| `retro` | create or refresh the retro artifact |
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
