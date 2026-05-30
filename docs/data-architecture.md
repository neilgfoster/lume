# Lume — Data and State Architecture

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0005

---

What state Lume holds, who owns it, how it flows, how context is stored/retrieved, and
where each category lives (local vs cloud). Resolves the storage mechanism deferred here
from the [orchestrator design](orchestrator-design.md) §3 and the context/confidentiality
obligations from [security requirements](security-requirements.md). Builds on
[agent boundaries](agent-boundaries.md). Requirements-level; concrete storage tech is a
**candidate pending a storage spike** (§6).

## Decisions (from the interview)

- **Workflow state is event-sourced (model) with the simplest build-now realisation.**
  The write-ahead step-intents + step-results Lume already records (WORK-0002) *are* an
  append-only event stream. **Build-now** is the minimal realisation: append those
  records + take **periodic snapshots** for fast current-state reads and bounded
  resume — *not* elaborate projection/replay machinery. Heavier event-sourcing tooling is
  **RESERVED**.
- **Context store is layered, structured-first.** **Build-now** = deterministic scoping +
  **structured slices** only. A **semantic vector store** (candidate: Chroma/Qdrant) is
  **RESERVED/opt-in** — built only when a fuzzy-retrieval need is demonstrated and
  WORK-0010 has selected a local embedding model. Compression is **local-model only**.
- **One store *contract*, per-category backing — but audit is excluded** (see §4):
  durable state sits behind a clean, swappable contract; build-now is **embedded/local**
  with no swap machinery; networked enterprise backends are RESERVED. The **audit log is
  not behind this orchestrator-callable contract** — it is a write-only emit to a
  separate trust domain (security §4).

---

## 1. State inventory

Format: **Category** — owner; lifetime; backing; tier. Confidentiality labels
(security §1) ride with any payload that can contain operator data.

- **Workflow state** (task, steps, write-ahead intents, step results, `applied_effects`)
  — orchestrator; until done/archived; append-only records + periodic snapshots; local.
- **Approvals** — orchestrator; until resolved (then audited); state store; local.
- **Grants** (earned autonomy) — policy (OPA); until expiry/revoke; policy store; local.
- **Audit log** — orchestrator (sole writer, write-only emit); permanent (configurable);
  append-only + signed in a **separate trust domain** (§4); local (durable).
- **Context store** — orchestrator; scoped (TTL/evict); **structured slices (build-now)**;
  vector + blob **RESERVED/opt-in**; local-first.
- **Registry** (capabilities/templates) — orchestrator; life of instance; KV;
  **RESERVED**; local.
- **Identity/permission context** — resolved per call (SPIRE); transient; not durably
  owned here; n/a.
- **Model-routing / cost counters** — orchestrator; rolling window; metrics store; local.

The orchestrator holds **no durable state in-process** (WORK-0002): every category above
lives in the store, so any instance can resume any workflow.

---

## 2. Data flow

How state moves between the orchestrator and the capabilities (the WORK-0002 §3 loop,
made concrete as events):

1. External client → `lume_task` → orchestrator **appends a `workflow-created` record**,
   returns `task_id` (status `planning`).
2. Inline planner produces the step plan → **`plan-recorded` record** (status `running`).
3. Per step: orchestrator **appends a `step-intent` record** (with the deterministic
   external identity for check-then-act) *before* acting → invokes the capability with
   **scoped, compressed context** (§3) → capability returns a structured result +
   `applied_effects[]` → deterministic VALIDATE → **`step-result` record** (orchestrator
   cross-checks `applied_effects` per security §3) → audit emitted.
4. Periodically: a **snapshot** of current workflow state is written for fast reads and
   to bound resume.

**Resume is side-effect-free.** A crashed instance rebuilds the current-state projection
by **replaying records from the latest snapshot — applying ZERO external effects** (it is
a pure in-memory reconstruction). External effects are re-attempted **only** by the
WORK-0002 check-then-act resume of the *single* uncommitted step (the one with a
`step-intent` but no `step-result`), gated on its recorded deterministic identity.
Replaying the event tail never re-pushes a branch or re-opens a PR.

Context never becomes durable orchestrator state; it is fetched, scoped/compressed,
handed to the capability for the step, and dropped.

---

## 3. Context store design

**Compression (always local).** Deterministic first — scope to the relevant slices,
truncate, extract structured fields. When a slice still exceeds the **target capability's
context budget** (a deterministic size check — the exact threshold is tuning, §6),
**summarise with a local model** (model-routing: "file summarisation → local model"). A
summarised or merged slice **inherits the most-restrictive confidentiality label of its
inputs**, so compression never launders a label (security §1).

**Storage (layered).**

- **Structured slices + metadata (build-now)** — typed fragments keyed by id/path/type;
  the default, cheap, reproducible.
- **Semantic/vector store (RESERVED/opt-in)** — embeddings for retrieval-by-meaning over
  large/fuzzy corpora (candidate: Chroma/Qdrant; embedding model → WORK-0010). Built only
  when a demonstrated fuzzy need exceeds deterministic search.
- **Blob store (opt-in)** — large raw payloads referenced by `context_id`.

**Retrieval.** Deterministic/structured query by default (by `context_id`, path, type).
The semantic path, when built, is selected by an **explicit flag/scope on the retrieval
request** (deterministic and testable) — *not* an LLM choosing the path (that would be a
control decision; Principle 1). Semantic *ranking* is non-deterministic, but retrieving
context is not a control-flow decision, so it is "inference where genuinely needed."

**Confidentiality (security §1).** Every payload is labelled at ingestion; the label is
integrity-bound and bound to the verified submitter identity (not self-declared), and it
**propagates through retrieval and compression** to the capability. Retrieval and any
cloud egress check the operator's confidentiality ceiling (label ordering defined in
security §1); an unverifiable label is treated as over-ceiling.

---

## 4. Durability mechanism

Durable state (except audit) sits behind a single **store contract** — clean and
swappable. **Build-now** is one embedded/local implementation behind a code seam, **no
multi-backend swap machinery**; networked enterprise backends are RESERVED and swap in
behind the same contract. The contract's operation surface (requirements altitude):
`append-record` / `read-snapshot` / `write-snapshot` / `get-by-id` / `list-by-type` (+ a
`blob put/ref` and a `vector query` slot once those tiers are built). Per-category
backing differs behind it.

- **Workflow** — append-only records + periodic snapshots; resume via projection rebuild
  (§2). Resume-only records are **compactable once a snapshot supersedes them**
  (retention distinct from audit — see below); this bounds event-log growth on a
  solo desktop. Snapshot cadence/compaction thresholds are tuning (→ spike).
- **Audit** — **NOT behind the store contract above.** Audit is a **write-only emit to a
  separate trust domain**; the orchestrator can append but cannot obtain a signing
  capability or mutate the chain (security §4: an attacker controlling the orchestrator
  must be unable to forge a signed record). It keeps its **own permanent signed chain**,
  independent of workflow-record compaction.
- **Context / grants / approvals / registry** — structured store / policy store / KV as
  in §1; registry RESERVED.

The orchestrator logic is identical across embedded and networked backends for the
contract-bound categories — the scale-agnostic requirement in storage. (Whether one
contract cleanly spans the deterministic categories *and* a future vector tier is a
question the spike must prove; the vector slot may end up a sibling interface — §6.)

---

## 5. Local vs cloud (per category)

**Local-first is the default for every category** (Principle 4); nothing is stored in a
third-party cloud service by default.

- **Workflow / audit / grants / registry** — local (durable). No third-party cloud by
  default.
- **Context payloads** — local. Only ever *sent* to a cloud model during escalation if
  at/below the confidentiality ceiling (security §1); never *stored* in cloud by default.
- **Model-routing / cost counters** — local; not applicable.

Two distinct claims, kept separate:

- **OSS / operator-controlled** — at enterprise scale the store may run on the operator's
  own networked infrastructure (not a third-party SaaS), OSS, behind the same contract.
  This satisfies must-not #1 (no lock-in to a paid third party).
- **Dependency hardness** — at multi-instance enterprise scale a networked store is in
  fact **required** (a single embedded store cannot serve many stateless orchestrator
  instances). The must-not-#1 guarantee there is that the store is OSS and
  operator-controlled and swappable — *not* that it is optional.

---

## 6. Known open questions / deferred

- **Storage-stack spike (not yet in the backlog)** — validate the append+snapshot
  realisation and (if/when built) the vector store (Chroma vs Qdrant); **prove the one
  store contract holds across the deterministic categories, or split the vector tier into
  a sibling interface**; measure **persist-per-step latency** (must not regress the
  solo-desktop feel, WORK-0002) and retrieval latency. Recommend adding a spike (raise
  with the plan, WORK-0014) — alongside the recommended security-stack spike.
- **Embedding + summarisation models** — selected in WORK-0010 (a Phase-1 blocker only
  if the semantic tier is built).
- **Context TTL / eviction** — route to the storage spike. **Invariant:** context
  referenced by an unfinished (incl. blocked/awaiting-approval) workflow is **not
  evicted**; define behaviour if an in-use `context_id` would expire.
- **Summarisation size threshold** — the exact context-budget threshold that triggers
  local-model summarisation (the *rule* — size-check vs the capability's budget — is
  fixed in §3; the *value* is tuning).
- **Snapshot cadence, compaction & replay bounds** — tuning, validated by the spike.
- **Enterprise networked backends & vector tier** — RESERVED; the contract admits the
  former without orchestrator change; the latter pending a demonstrated need.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
