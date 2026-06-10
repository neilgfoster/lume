# Lume — Constraints, Non-negotiables & Decision Log

> **Status (2026-06-10).** The **Constraints** and **Non-negotiables** below are
> *current* — they still govern lume and have held across all eight closed
> workstreams (and this ninth in progress)
> (stdlib-only, deterministic over inference, no auto-commit, ceremony-buys-its-cost).
> The **Decision log** at the end is a *historical record* dated 2026-06-09,
> preserved as the original rationale; later per-workstream decisions live in each
> workstream's `decisions.json`. One constraint to note as evolved: "no server,
> no database" still holds, and lume now also ships as a Claude Code plugin. For
> current state, see the [README](../README.md).

## Constraints
- **Operator time:** the defining constraint. Time-poor; works in short, interrupted bursts (≈15–25 min dip-in sessions), often days apart, often across several parallel workstreams. Hard time budget not numerically fixed — "lightweight" is measured against this.
- **Stack:** Claude Code + plain markdown/JSON files + git. No server, no database, no external services in v1. (To be confirmed if any external dependency proves unavoidable — see questions.)
- **Execution:** synchronous only — work happens inside a live session. No unattended/background execution.
- **Team:** solo (the author) for v1.

## Non-negotiables
- **No auto-commit.** Claude never commits without explicit consent; the operator reviews changes to rebuild context before deciding.
- **No crossing an iteration boundary without consent.** One iteration per consent.
- **DoD-gated iterations.** An iteration is driven by a DoD the operator approves at the opening boundary.
- **Deterministic over inference** for control flow, state transitions, and gates. Inference is reserved for the actual work, not the mechanism.
- **Ceremony must buy back more time than it costs.** Every gate, DoD, and snapshot must visibly save more operator time than it spends, or it gets cut. This is the constitutional principle; it overrides feature ambition.
- **Stay true to intent.** Lume should resist growing into something it was never meant to be. Audit against Claude Code native features and deprecate Lume features once superseded — Lume is scaffolding that should shrink as the platform grows. A future guardrail: Lume adversarially reviews the operator's own decisions to keep this honest.
- **Human-readable, diffable state.** Files, not opaque stores.
- **Design for replaceability.** Core components sit behind contracts (tracking, review, practice).

## Decision log (historical, 2026-06-09)
| Date | Decision | Rationale |
|---|---|---|
| 2026-06-09 | Execution is synchronous (World A); unattended execution is out of scope, possibly a separate project. | Tractable now; unattended autonomous loops are a large, separate technical risk Claude Code doesn't natively support. |
| 2026-06-09 | Iterations are short (~15 min), reviewable, DoD-gated; no auto-commit; one consent per boundary. | Matches dip-in working style and preserves operator control/context-rebuilding. |
| 2026-06-09 | Work nests arbitrarily (Epic/Story/Task); decomposition is itself an iteration. | Vague/changing scope fractals naturally; mirrors the author's iterative breakdown style. |
| 2026-06-09 | Primary surface is a flat "awaiting review" queue collapsing the tree; tree is for filing, queue is for operating. | Daily triage is "what's waiting on me," then drill in and advance. |
| 2026-06-09 | Continuity carried by a living Done/Now/Next snapshot per workstream. | Directly answers the three recall failures (what's next, why, where). |
| 2026-06-09 | Approve at every level in v1; earned delegation (reputation) is directional, later. | Keep v1 simple and fully under control; relax only once Claude's self-review track record is measured. |
| 2026-06-09 | Storage location is configuration (detached/invisible vs embedded/in-repo); format constant. v1 = embedded. | Portability without leaking files into other repos; embedded enables future handover. Detached deferred. |
| 2026-06-09 | Multi-operator handover is directional, not v1; format must keep it possible. | Real collaboration value, but scope-heavy (identity, locking, per-operator trust). |
| 2026-06-09 | First slice = dogfooding: Lume builds Lume. | Self-proving validation on a real, fragmented, multi-session project. |
| 2026-06-09 | Decomposition/nesting is the first thing cut under pressure; linear single-workstream loop is the irreducible core. | Keeps the MVP honest and minimal. |
| 2026-06-09 | Contracts are in v1 for tracking, review, and workstream practice — even with single implementations. | Good foundations for expansion; don't reinvent PM tooling; allow review panels and per-objective practices later. |
| 2026-06-09 | Each contract must be designed against two concrete implementations (its example pair); v1 hardcodes one path expressed as data, doesn't fully abstract until a second implementation pulls on it. | Cheapest insurance against single-implementation contracts that leak. |
| 2026-06-09 | "Ceremony exceeds value" is the headline risk and a design constraint, not just a worry. | A time-saving framework that spends time will be routed around and abandoned. |
| 2026-06-09 | Adversarial review of the operator's own decisions is a directional guardrail to prevent scope creep. | Keep Lume true to its intent; stop it growing into something it was never meant to be. |

---
Design records: [vision](vision.md) · [scope](scope.md) · [questions](questions.md) · current state: [README](../README.md)
