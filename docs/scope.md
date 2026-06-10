# Lume — Scope

> **Status: historical design record (2026-06-09).** This is the original v1
> scope plan, written before the build. It is preserved as-is, not maintained.
> Much of the "v1 spine" and priority sequence has since shipped; some deferred
> items are still deferred. A quick reconciliation against what was actually
> built is at the end of this file. For current state, see the
> [README](../README.md).

## v1 spine (the smallest thing that delivers value)
The first slice is whatever Lume needs to **manage its own construction as a single workstream**. If Lume can't help build Lume, it has failed its own test.

The minimal loop, on a **single flat workstream**:

1. **Create a workstream** with an objective, stored as files in the repo.
2. **Open an iteration:** propose a DoD; operator approves. (Gate that starts work.)
3. **Run the iteration:** Claude does ~15 min of work and self-reviews adversarially against the DoD, redoing until it believes the DoD is met.
4. **Hand back:** Claude presents what changed plus an updated **Done / Now / Next** snapshot. **No auto-commit.**
5. **Accept or reject:** accept → open next iteration; reject with reasons → redo this iteration, DoD refined if needed.

## In scope for v1
- The linear iteration loop (steps 1–5) on one workstream.
- File-based state in the repo (**embedded mode**): objective, DoD per iteration, decisions, Done/Now/Next snapshot. Human-readable and diffable.
- Adversarial self-review against the DoD before hand-back (minimal reviewer; see contracts).
- Hard gates: no crossing an iteration boundary without consent; no commit without consent.
- **Contracts defined in v1** for the three seams below, even where only one implementation ships. Each contract must express *both* members of its example pair cleanly (the design test).

### The three contracts (foundations for expansion)
| Contract | v1 implementation | Future implementation it must admit |
|---|---|---|
| Tracking / persistence | Local files (self-tracking) | GitHub Issues, Jira, other PM tools |
| Review | Single minimal reviewer | Multi-agent review panels / different models per purpose |
| Workstream practice | One hardcoded step-sequence, expressed as data/config | Templates: research (*discover → research → build → dispose*), delivery (*iterate → refine → iterate*), agile, waterfall, TDD, SDD |

## Out of scope for v1 (deferred, but not precluded)
- **Decomposition / arbitrary nesting** — desirable, but the first thing to cut under pressure. Start flat; add nesting when the wall is hit.
- **Flat cross-forest review queue** — trivial with one workstream; build when multiple workstreams are live.
- **Detached / invisible mode** — running Lume on other repos without leaking files. (Embedded mode first.)
- **Multi-operator** identity, locking, handover.
- **Reputation / delegation** model to relax approval gates.
- **Adversarial review of the operator's own decisions** — a guardrail where Lume challenges the author's choices to prevent scope creep and keep Lume true to its intent. Directional; not v1. (See questions.)
- **Lume self-improvement** from real-world usage (the dogfooding spine is its primitive seed).
- Populating the configurable step-pipeline with multiple real templates; multi-agent panels.

## Rough priority sequence
1. Linear loop on a single workstream (the spine) + file-based embedded state.
2. The three contract seams, designed against their example pairs.
3. Decomposition / nesting.
4. Flat cross-forest review queue.
5. Detached/invisible mode.
6. Templates + configurable step pipelines populated; multi-agent review panels.
7. Multi-operator handover; reputation/delegation; self-improvement; adversarial review of operator decisions.

## First slice of work
Stand up steps 1–5 as a runnable loop, and use it immediately to run "build Lume" as workstream #1. Express the iteration step-sequence as data so templates are a later population of an existing shape, not a rewrite.

## Where we cut first under pressure
Decomposition (nesting) goes first. The linear single-workstream loop is the irreducible core.

## Reconciliation: plan vs what shipped (2026-06-10)
Against the priority sequence above:
1. **Linear loop + file-based embedded state — shipped** (workstreams 0001–0003): the loop runs, state is schema-validated JSON, markdown is a derived view.
2. **The three contract seams — partially shipped.** Tracking/persistence is behind a `TrackingStore` seam with a filesystem implementation (0004 swappable-backing, 0007 id-keyed store); review and workstream-practice contracts are *designed*, not built out (single reviewer, the discovery→planning→execution→closeout lifecycle is the one practice).
3. **Decomposition / nesting — not built** (still the first thing cut).
4. **Flat cross-forest review queue — partial:** `lume status` with no `-w` renders an "awaiting review / in progress" queue across workstreams; nesting-aware collapsing is not built.
5. **Detached / invisible mode — not built.** State is still embedded in the target repo's `.lume/`.
6. **Templates + multi-agent panels — not built.**
7. **Multi-operator / reputation / self-improvement — not built** (directional).

Not in the original sequence but shipped: **packaging as an installable Claude Code plugin** (0008), and an agent-friendly CLI with a self-describing verb catalog (0005–0006). What's deferred above is deferred on purpose, not forgotten.

---
Design records: [vision](vision.md) · [constraints](constraints.md) · [questions](questions.md) · current state: [README](../README.md)
