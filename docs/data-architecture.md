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
[agent boundaries](agent-boundaries.md).

It is requirements-level; concrete storage tech and tuning go to a storage spike (§6).

## Decisions (from the interview)

- **Workflow state is hybrid event-sourced** (event-first): an append-only event stream
  (the write-ahead step-intents + step-results from WORK-0002 *are* the events) with
  **periodic snapshots** for fast current-state reads and bounded replay. Resume =
  replay-from-snapshot; the event stream dovetails with the append-only audit log.
- **Context store is layered:** deterministic scoping + structured slices by default;
  a **semantic vector store (wrap Chroma/Qdrant)** as an opt-in retrieval mechanism for
  large/fuzzy cases; **compression is local-model only** (never cloud).
- **One store *contract*, per-category backing semantics.** All durable state sits behind
  a clean, swappable store contract; build-now is **embedded/local**; networked
  enterprise backends are RESERVED (swapped in behind the same contract).

---

## 1. State inventory

Every category Lume holds, with owner, lifetime, and storage tier. Confidentiality
labels (security §1) ride with any payload that can contain operator data.

Format: **Category** — owner; lifetime; backing; tier.

- **Workflow state** (task, steps, write-ahead intents, step results, `applied_effects`)
  — orchestrator; until done/archived; event stream + snapshots; local.
- **Approvals** — orchestrator; until resolved (then audited); event/state store; local.
- **Grants** (earned autonomy) — policy (OPA); until expiry/revoke; policy store; local.
- **Audit log** — orchestrator (sole writer); permanent (configurable); append-only +
  signed with the key in a separate trust domain; local (durable).
- **Context store** — orchestrator / context capability; scoped (TTL/evict); structured +
  vector + blob; local-first.
- **Registry** (capabilities/templates) — orchestrator; life of instance; KV;
  **RESERVED**; local.
- **Identity/permission context** — resolved per call (SPIRE); transient; not durably
  owned here; n/a.
- **Model-routing / cost counters** — orchestrator; rolling window; metrics store; local.

The orchestrator holds **no durable state in-process** (WORK-0002): every category above
lives
in the store, so any instance can resume any workflow.

---

## 2. Data flow

How state moves between the orchestrator and the capabilities (the WORK-0002 §3 loop,
made concrete as events):

1. External client → `lume_task` → orchestrator **appends a `workflow-created` event**,
   returns `task_id` (status `planning`).
2. Inline planner produces the step plan → **`plan-recorded` event** (status `running`).
3. Per step: orchestrator **appends a `step-intent` event** (with the deterministic
   external identity for check-then-act) *before* acting → invokes the capability with
   **scoped, compressed context** (§3) → capability returns a structured result +
   `applied_effects[]` → deterministic VALIDATE → **`step-result` event** (orchestrator
   cross-checks `applied_effects` per security §3) → audit record appended.
4. Periodically: a **snapshot** of current workflow state is written for fast reads and
   to bound replay.
5. Gate → status `awaiting_approval` (durable; no held process). Completion → final
   result assembled from the projection; status `done`; audit finalised.

Context never flows into the orchestrator's process as durable state; it is fetched from
the context store, scoped/compressed, handed to the capability for the step, and dropped.
A crashed instance **replays from the latest snapshot + subsequent events**.

---

## 3. Context store design

**Compression (always local).** Deterministic first — scope to the relevant slices,
truncate, extract structured fields. When a slice is still too large, **summarise with a
local model** (model-routing: "file summarisation → local model, never burn cloud
tokens"). Capabilities receive only the compressed, scoped context (Principle 3).

**Storage (layered).**

- **Structured slices + metadata** — the default: typed fragments keyed by id/path/type.
- **Semantic/vector store** — *opt-in* (wrap Chroma/Qdrant): embeddings for
  retrieval-by-meaning over large/fuzzy corpora. The embedding model is local
  (candidate/selection → WORK-0010).
- **Blob store** — large raw payloads referenced by `context_id`.

**Retrieval.** Deterministic/structured query by default (by `context_id`, path, type —
cheap, reproducible). Semantic vector search is the opt-in path when deterministic search
is insufficient. Semantic ranking is non-deterministic, but retrieving *context* is not a
control-flow decision, so it is "inference where genuinely needed", not a Principle-1
violation.

**Confidentiality (security §1).** Every payload is labelled at ingestion, the label is
integrity-bound and bound to the verified submitter identity (not self-declared), and it
propagates with the payload. Retrieval and any cloud egress check the operator's
confidentiality ceiling; an unverifiable label is treated as over-ceiling.

---

## 4. Durability mechanism (per-category backing behind one contract)

All durable state sits behind a single **store contract** (clean, swappable). Build-now
is an embedded/local implementation; networked enterprise backends are RESERVED and swap
in behind the same contract. Backing semantics differ per category:

- **Workflow** — event store (append-only events) + periodic snapshots; replay for
  resume. Snapshot cadence and replay bounds are tuning (→ spike).
- **Audit** — append-only and signed, with the signing key in a **separate trust domain**
  from the orchestrator (security §4) — *not* the same backend as workflow events even
  though both are append-only.
- **Context** — structured + vector + blob (above).
- **Grants / approvals** — policy/state store; grants carry expiry (security §2).
- **Registry** — KV, RESERVED.

The orchestrator logic is identical across embedded and networked backends — the
scale-agnostic requirement expressed in storage.

---

## 5. Local vs cloud (per category)

**Local-first is the default for every category** (Principle 4); nothing is stored in a
third-party cloud service by default.

- **Workflow / audit / grants / registry** — local (durable). No third-party cloud by
  default; an operator-run networked backend at enterprise scale is not a third-party
  SaaS (RESERVED, swappable).
- **Context payloads** — local. Only ever *sent* to a cloud model during escalation if
  at/below the confidentiality ceiling (security §1); never *stored* in cloud by default.
- **Model-routing / cost counters** — local; not applicable.

"Cloud" here means an external/third-party service. Running the store on the operator's
own networked infrastructure at enterprise scale is local-by-trust, behind the same
contract and opt-in — never a hard dependency (must-not #1).

---

## 6. Known open questions / deferred

- **Storage-stack spike (not yet in the backlog)** — validate the event store + snapshot
  mechanism and the vector store (Chroma vs Qdrant) in the devcontainer; measure the
  **persist-per-step latency** (WORK-0002 flagged this must not regress the solo-desktop
  feel) and retrieval latency. Recommend adding a spike (raise with the plan, WORK-0014) —
  alongside the recommended security-stack spike.
- **Embedding + summarisation models** — the local models for embeddings and context
  summarisation are selected in WORK-0010.
- **Context TTL / eviction policy** — how long scoped context lives and how it is evicted.
- **Snapshot cadence & replay bounds** — tuning, validated by the spike.
- **Enterprise networked backends** — RESERVED; the store contract admits them without
  orchestrator change.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
