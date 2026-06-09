# Lume — Vision

## One-sentence version
Lume is a lightweight framework for Claude Code that lets a time-poor operator run real work across many short, interrupted sessions — sometimes days apart — without losing the thread.

The name evokes *loom* (to weave): keeping a continuous fabric of work intact even when you only touch the loom in short bursts.

## Why this exists
Work spans multiple sessions and days, often with gaps in between, and frequently several workstreams run in parallel under one operator. When you return after a gap, specific things have decayed:

- You can't remember **what came next**.
- You can't remember **why** decisions were made.
- You can't remember **where things are up to**.
- Claude has **lost context** and may act inconsistently with earlier work.
- Large problems fractal into workstreams that spawn workstreams, and you **lose the map**.

The decomposition mechanism that breaks big work into smaller work is exactly what causes the context-loss it's meant to manage. Orientation is therefore a first-class problem, not a side effect of good record-keeping.

## What's different if it succeeds
You can dip in for 15–25 minutes, re-orient in about a minute, review what changed while you were away, move each workstream forward, and leave — repeatedly, across days — and the work stays coherent.

## Primary user and job-to-be-done
- **Primary user (v1):** the author, a time-poor operator running multiple parallel workstreams through Claude Code.
- **Job:** "When I sit down for a short, interrupted burst, help me re-orient instantly, trust the work done since I left, and push each workstream one safe step forward — without me holding the whole tree in my head."
- **Directional (not v1):** other operators pick up and run each other's workstreams, with decisions and intent surviving the handover (reduces handover cost, preserves context between people). The state format should make this *possible* later; v1 does not build operator identity, locking, or per-operator trust.

## The core model
- A **workstream** is a sequence of **iterations**.
- An **iteration** (~15 min wall-clock, synchronous) has a type and its own **Definition of Done (DoD)**.
- Iteration lifecycle: **propose & approve DoD** → **Claude works, self-reviewing adversarially against the DoD** → **hand back (no auto-commit)** → **operator accepts (next) or rejects (redo, better informed)**.
- Work nests arbitrarily: a workstream whose iterations are themselves workstreams (Epic → Story → Task). Decomposition is itself just an iteration.
- **The tree is the filing cabinet; the queue is the inbox.** Work is filed as an arbitrarily deep tree, but the daily driver is a flat "what's waiting on my review" queue that collapses the tree.
- Continuity is carried by a living **Done / Now / Next** snapshot per workstream — what's been done and why, where we are, where we're going — kept current at every iteration boundary.

## Execution model
Synchronous (World A): Claude runs an iteration while the session is open; you launch it, it completes in a short burst, and you review now or next time. **Unattended/background execution is explicitly out of scope** — that may be a separate, later project.

## Bootstrap philosophy
Lume is scaffolding, not a destination. Its job is to make the author effective enough to build bigger products — possibly including Lume's own successor. It earns its keep by being *used*, not by being finished. Bias toward simple-and-usable-now over complete-and-elegant. A standing intent: Lume should keep itself honest and resist growing into something it was never meant to be (see constraints and questions).

## Success
- **Leading signal:** Lume is used to build Lume, and helps rather than hinders — the author keeps choosing to use it on its own development.
- **Lagging outcome:** Lume is good enough to point at another repo.
- The first slice is dogfooding: Lume development is just another workstream, run through Lume.

## Non-goals (v1)
- Unattended / background autonomous execution.
- Multi-operator identity, locking, and handover machinery (kept *possible*, not built).
- Reputation/delegation model that relaxes approval gates (directional only).
- A polished product for general users.
- Reinventing project-management tooling (Lume starts by tracking itself; external PM tools are a later swap behind a contract).
