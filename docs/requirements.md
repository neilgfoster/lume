# Lume — Core Requirements

**Status**: in review (revised after adversarial review; awaiting re-approval)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0001

---

This document records *what Lume must be and do* at the requirements level. It
contains no architecture decisions and no implementation detail — those belong
to the design docs and ADRs that follow.

**Relationship to `CLAUDE.md`.** `CLAUDE.md` currently frames Lume narrowly as an
IDP and is *not* changed by this document. Reconciling it is tracked as a separate
follow-up (**WORK-0015**) and must not be assumed done. Until that lands, the
governing rule is: **for Lume's vision, scope, and the must-nots in section 3,
this document governs; for Phase 0 process, gates, and review discipline,
`CLAUDE.md` governs.** Where the two still conflict on vision, this document is
the corrected, broader intent.

---

## 1. Vision

**Lume is an extensible, AI-native platform for building and operating
AI-centric products without hard dependency on any third party.**

- **Independence is the north star.** Build AI-centric products and tools
  without being tied to third parties. Local-hosted models by default; cloud LLM
  services (e.g. AWS Bedrock) or self-built models when it suits the operator —
  never out of lock-in.
- **Scale-agnostic.** The same platform runs from a single desktop to the cloud,
  serving a solo user up to an entire enterprise on one model.
- **Complementary competitor.** Lume can replace a tool like Claude Code, or work
  alongside it. It can be a full platform or just the pieces an operator needs.
  The balance is always an operator choice.

### Two layers of extensibility

- **Capabilities** — native, modular abilities (e.g. MIDI, email, sub-agents,
  research, coding, provisioning). The building blocks.
- **Templates** — pre-configured collections of capabilities fitted to a
  use-case (e.g. full SDLC, research, personal assistant, TTRPG GM). A template
  is the starting scaffold an instance is provisioned from; capabilities are the
  parts it is composed of.

Lume can **build new capabilities**, which in turn unlock new templates. Nothing
stops an operator from **composing existing capabilities into new templates**
themselves.

### Self-extending and federated

Lume builds itself. Operators build capabilities to solve their own use-cases,
and those capabilities can **feed back into Lume** — shareable and improvable by
others, like a registry/exchange. The platform is modular by design so that
contribution flows both ways.

### The SDLC template is the bootstrap, not the destination

The software-build-and-operate capability (the "IDP") is the **first template**.
It is the pattern that lets Lume build itself and every future capability and
template. The ultimate scope is open-ended: personal assistant, a one-operator
startup (operator as the only human, Lume as every other role), AI music creation
via MIDI, a real-time voice TTRPG game master, and beyond.

**Phase discipline note:** the full vision above is recorded intentionally, but
**Phases 0–1 deliberately focus only on the SDLC template as the bootstrap.**
Everything else is future scope and must not pull work forward.

### The bootstrap arc (HEDL → Lume)

1. Claude Code only.
2. Claude Code + **HEDL** — HEDL provides an AI-centric SDLC discipline framework
   used to build Lume.
3. Lume starts building itself, baking in the learnings from HEDL.
4. Lume is fully independent — usable by anyone, with any (or no) third-party
   tooling.

HEDL is **not a throwaway proof-of-concept**. It is the AI-centric foundation
that gets Lume off the ground and has standalone value. It may become redundant
as Lume's own capabilities grow, or it may persist as the foundation for other,
non-Lume projects.

---

## 2. Users and pain

- **Neil (operator)** — first 3 months, the only realistic user. Needs to
  realise more of his ideas within a fixed budget and a realistic timeframe.
- **Small teams** — later. Adopt Lume incrementally alongside existing tooling.
- **Whole organisations** — later (vision). Run software delivery, and
  eventually whole business functions, on Lume.

**The primary pain:** ambitions outrun budget. The cost of frontier AI usage
(Claude Code on a Pro plan) caps how much can be built. The first job of Lume is
to absorb the **grunt work** onto local models so that fixed budget goes further.
*Grunt work* here means low-novelty or deterministic tasks a local model can
complete within validation limits — as distinct from the frontier-only work that
genuinely needs a cloud model.

**Incremental adoption is a requirement, not a nice-to-have.** Lume must never be
all-or-nothing. The system requirement: **any subset of responsibilities can be
offloaded to Lume — and revoked — at any time**, with the rest staying on the
operator's existing tools. This spans the full range from "Lume for simple stuff
only" to "Lume for everything." Which subset is active is the operator's choice
at all times.

---

## 3. Must-nots

Hard lines and default postures Lume must honour.

### Hard lines (never crossed)

1. **No tech-stack lock-in.** Lume must never tie the operator to a particular
   third-party tech stack. Everything modular, everything swappable, with clean
   contracts providing abstraction at every level. A *clean contract* here means a
   typed boundary that hides the vendor behind it, such that swapping the
   implementation requires no change to callers. The hard line is on the
   *principle*, not on any technology — current defaults (e.g. Kubernetes, Ollama)
   are permitted precisely because they sit behind such contracts and stay
   swappable.
2. **No private data to third parties without explicit opt-in.** Private code or
   data must never be sent to a cloud model or external service unless the
   operator has explicitly opted in.
3. **No LLM-inferred control flow.** The LLM must never infer success, failure,
   or what to do next. Those are always deterministic outputs. (A core HEDL
   fundamental, carried into Lume.)
4. **Use inference only where it is genuinely needed.** Everything else is
   deterministic. The decision rule is concrete (per `CLAUDE.md`): *if a function
   can do it, an LLM must not.* "Genuinely needed" means no deterministic
   function or lookup can produce the output. This is possibly *the* central
   engineering principle, ranked alongside independence.

### Permanent discipline

5. **Permanent existential discipline.** Do not build what already exists unless
   building is genuinely justified. No sunk-cost fallacy — be brutal and kill
   things that are not earning their place, even after they are built. Always
   strive for simplicity. Do not build what others already do much better. Lean
   on cutting-edge open-source rather than reinventing it.

### Default postures (graduated, can be relaxed as autonomy is earned)

6. **High-blast-radius changes are human-gated by default.** Lume does not
   auto-approve its own high-impact changes initially.
7. **Irreversible real-world actions are human-gated by default** — deleting
   data, spending money, sending external communications (email, voice, posts).

   Postures 6 and 7 are **not fixed**. Lume operates an **earned-autonomy model**:
   it can gain more autonomy over time by demonstrating reliability — measured on
   the rate of validated-correct outputs within a given blast-radius class (e.g.
   via adversarial review and a track-record signal). As Lume proves it does
   things right, guardrails can be relaxed. The system must be *capable* of safely
   relaxing them; the threshold and mechanism are a design concern, not a
   requirement here.

   **Deliberate revision of `CLAUDE.md`.** This earned-autonomy posture
   intentionally supersedes `CLAUDE.md`'s current absolute rule that *"High always
   requires human approval — no exceptions."* Under the earned-autonomy model that
   rule becomes the *default*, not a permanent absolute. Resolving the wording in
   `CLAUDE.md` is part of the reconciliation tracked as **WORK-0015**.

---

## 4. Success metrics

**Headline outcome — leverage at fixed cost.** Lume succeeds if the operator
**delivers more per fixed budget.** The counted unit is **delivered work items /
merged PRs per month**, compared against the pre-Lume baseline. "Fixed budget"
means **no new paid spend beyond the existing Claude Code Pro plan** (token usage
within that plan may not drop — and that is fine, because freed tokens are
redirected to the genuinely hard, frontier-only problems while Lume absorbs the
rest). There will always be more ideas than budget; Lume's first measure of
success is enabling more of those ideas to be realised in a realistic timeframe.
Precise numeric targets and the baseline window are deferred (see open
questions).

**Diagnostic indicators** (explain *why* throughput rose):

| Indicator | What it signals |
|-----------|-----------------|
| Offload ratio | Share of tasks completed locally by Lume vs. escalated to cloud/Claude |
| Self-built capabilities | Count of Lume capabilities or fixes that Lume itself produced |
| Trust earned | Number of action classes graduated from "human-gated" to "autonomous" |
| Time-to-done | Time to complete routine tasks / time-to-PR |

The headline metric is the one to watch; the diagnostics exist to explain
movement in it. Precise targets are deferred (see open questions).

---

## 5. Integration constraints

**Governing principle:**

> You cannot build Lume without some opinions. But as Lume is built, those
> opinions become **options** that can be replaced later. Initial tech choices
> are defaults, not commitments — every one must sit behind a clean contract so
> it can be swapped.

There are **no permanent technology constraints.** The only non-negotiables are
the *principles* (independence, determinism-over-inference, no lock-in,
modularity, validation loops, the earned-autonomy posture).

- **HEDL** — a must, for now. The foundation that gets Lume off the ground
  (including work tracking). This is an **acknowledged bootstrap-period
  dependency**, not a counter-example to the no-lock-in hard line: that line
  forbids creating *new permanent* lock-in, and HEDL's long-term fate is an
  explicit open question (see section 6). It may become redundant as Lume's
  capabilities grow, or persist for non-Lume projects.
- **Kubernetes** — current best answer for scaling from one desktop to
  enterprise. **Not a permanent constraint** — open to alternatives; sits behind
  a clean contract like everything else.
- **Claude Code + Claude Pro** — integrated now because it is what the operator
  has access to. An opinion — any AI tool could be supported. Swappable.
- **Local model runtime (Ollama)** — current default. Swappable later.
- **Work tracking** — provided by HEDL today; follows HEDL's trajectory.
- **Git host (Gitea / GitHub)** — current default behind a clean contract;
  swappable.

---

## 6. Known open questions

These are **deliberately deferred** — recorded as known unknowns, to be resolved
as the work proceeds rather than up front.

- **Earned-autonomy mechanism** — how does Lume concretely *prove* enough
  reliability to relax a guardrail? Reputation and adversarial-review thresholds
  are undefined.
- **Federated capability sharing** — the registry/exchange that lets
  capabilities flow between instances is a large, undesigned area.
- **HEDL's long-term fate** — absorbed into Lume, kept alongside, or deprecated.
  Explicitly undecided.
- **Local model capability ceiling** — will local models be good enough for the
  grunt work, or will too much escalate to cloud and undermine the leverage
  thesis?
- **Real-time / voice modality** — the TTRPG-GM / voice use-case has a very
  different latency and modality profile from batch SDLC work; unknown whether
  the same core serves it.

---

## Sign-off

- [x] Neil approved the original draft (2026-05-30).
- [ ] **Neil has re-approved after adversarial-review revisions.**

*`CLAUDE.md` reconciliation to the broader "platform + capabilities + templates"
framing is tracked as **WORK-0015** — not done in this document.*
