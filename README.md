# lume

[![CI](https://github.com/neilgfoster/lume/actions/workflows/ci.yml/badge.svg)](https://github.com/neilgfoster/lume/actions/workflows/ci.yml)

lume is a deterministic, operator-gated iteration loop for doing real work with
an AI agent across short, interrupted sessions without losing the thread. It
tracks **workstreams** (goals), breaks them into **gated iterations**, and keeps
all state as inspectable JSON in your repo. No LLM runs inside lume itself — it
reads, validates, and writes state; the thinking happens in the work, never in
the mechanism. Its one rule: **the machine does not act without the operator.**

It ships as a Claude Code plugin.

## Why you should NOT use lume (read this first)

This section is deliberately first. lume is early and honest about it.

- **It has exactly one user: its author.** There are zero external adopters
  (see [ADOPTERS.md](ADOPTERS.md)). Nothing here has been pressure-tested by
  anyone but the person who wrote it. *[U] — unevidenced for anyone else.*
- **Its central promise is unmeasured.** lume's whole bet is that the ceremony
  (defining a DoD, gates, snapshots) *buys back more time than it costs*. That
  has never been measured. There is no time-saved metric, no study, nothing —
  just the author's continued use. *[U] — see [docs/questions.md](docs/questions.md), assumption 4.*
- **lume grades its own homework.** Every iteration was reviewed by the same
  person who commissioned it — a sample of one. "Claude's self-review is honest"
  is assumed, not quantified (no reject-rate data). *[U].*
- **The install has never run in a live Claude Code session.** It is verified
  only by an automated smoke test driving the bundled binary on a throwaway
  repo. *[U] — see the [0008 retro](.lume/workstreams/0008-package-as-claude-plugin/retro.json).*
- **It fits one narrow working style.** It is built for a time-poor operator
  juggling parallel workstreams in 15–25 minute bursts. If you don't work that
  way, the overhead probably won't pay off. *[U] — it's a design target, not a tested claim.*
- **Synchronous and solo only.** No background/unattended execution; no
  multi-operator, identity, or locking. *[E] — by design; see [docs/constraints.md](docs/constraints.md).*
- **It's meant to shrink.** lume is scaffolding intended to be superseded by
  native Claude Code features over time, not a product to depend on. *[E] —
  stated non-negotiable in [docs/constraints.md](docs/constraints.md).*
- **It is v0.1.0.** Expect rough edges and breaking changes.

If you need something proven, multi-user, or measured, lume is not it yet.

## What lume can honestly claim

Only what there's evidence for:

- **It works mechanically and is tested.** 313 passing tests (`python3 -m pytest`). *[E].*
- **Zero runtime dependencies.** Pure Python stdlib; no server, no database, no
  packages to install beyond `python3`. *[E] — see the source under `plugin/src/lume/`.*
- **It installs as a plugin and bootstraps a fresh repo.** `lume seed` creates
  `.lume/` and the first workstream on a repo that isn't this one. *[E] —
  covered by a clean-repo smoke test (`tests/test_smoke_install.py`); but see
  the live-session caveat above.*
- **It was used to build itself.** lume was developed across eight closed
  workstreams run through lume (a ninth, this docs refresh, in progress) — the
  full record is in `.lume/workstreams/`. *[E].*

## Install

Requires `python3` on your PATH. In Claude Code:

```
/plugin marketplace add neilgfoster/lume
/plugin install lume@lume
```

This install path is verified two ways: an automated smoke test
(`tests/test_smoke_install.py` drives the entry point end to end) and a live
human run — `/plugin marketplace add` + `/plugin install`, then `lume seed` /
`lume status` / `lume check`, exercised in the `tredl` adopter repo on
2026-06-11. For local development you can instead run
`claude --plugin-dir /path/to/lume/plugin`.

Then, from the repo you want to work in:

```
lume seed       # bootstrap: creates ./.lume/ and a seed workstream (your first step)
lume status     # orient: objective, current phase, Done / Now / Next
```

The full user guide — the iteration loop, every verb, conventions — is in
[plugin/README.md](plugin/README.md).

## The loop, briefly

```
lume seed                   # first time on a repo
lume status                 # orient
lume open "<title>"         # open the next iteration (refused unless the last is accepted)
   ... draft a binary Definition of Done ...
lume approve                # operator: the DoD is good
lume start                  # work begins
   ... do the work, write an honest self-review ...
lume handback               # hand back for review
lume accept                 # operator: done   (or: lume reject "<reason>" -> lume redo)
```

## This repository

This is lume's development repo; it is also where lume dogfoods itself. It is
laid out so only the plugin ships to adopters:

```
plugin/                  # the installable plugin (this is what gets installed)
  .claude-plugin/plugin.json
  bin/lume               # entry point (on PATH when installed)
  src/lume/              # the engine (stdlib-only Python package)
  skills/lume/           # the guiding skill
  README.md              # the user guide
.claude-plugin/
  marketplace.json       # marketplace entry; source -> ./plugin
tests/                   # the test suite + conftest.py (dev only, not shipped)
docs/                    # design records (dev only)
.lume/                   # lume's OWN workstream state (dev only, not shipped)
ADOPTERS.md              # who uses lume (currently: just lume)
```

The marketplace points its plugin `source` at `./plugin`, so installing lume
brings only `plugin/` — `.lume/`, `tests/`, and `docs/` stay out of an adopter's
cache.

### Develop / test

```
python3 -m pytest                                                 # conftest puts plugin/src on the path
PYTHONPATH=plugin/src python3 -m unittest discover -s tests -t .   # stdlib runner
plugin/bin/lume status                                            # drive lume in this repo
```

CI (`.github/workflows/ci.yml`) runs the suite on push and every PR across
Python 3.11-3.13. Making that check **required** for merge is a branch-protection
setting the repo operator enables on GitHub — the workflow provides the signal,
the operator decides whether it blocks.

## Design records

These are historical design documents (2026-06-09), preserved and banner'd —
they describe original intent, reconciled against what shipped:

- [docs/vision.md](docs/vision.md) — why lume exists, the core model
- [docs/scope.md](docs/scope.md) — v1 plan vs what shipped
- [docs/constraints.md](docs/constraints.md) — current constraints + historical decision log
- [docs/questions.md](docs/questions.md) — assumptions & risks, reconciled (the unmeasured ones flagged)

## Status & evidence

The load-bearing claims and where they stand:

| Claim | Standing |
| --- | --- |
| 313 tests pass; deterministic; stdlib-only | **[E]** test suite + source |
| Installs as a plugin; `lume seed` bootstraps a fresh repo | **[E]** smoke test — but **[U]** never run in a live session |
| Used to build itself across 8 closed workstreams | **[E]** `.lume/workstreams/` |
| Saves more operator time than its ceremony costs | **[U]** unmeasured — lume's biggest open claim |
| Self-review is honest enough to trust handbacks | **[U]** no reject-rate data |
| Works for anyone but the author | **[U]** zero external users |

`[E]` = evidenced, with a citation. `[U]` = not yet evidenced. lume will not
claim `[E]` for anything it cannot point at.
