# Lume — Orchestrator Design

**Status**: in review
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0002

---

This document is the design of the **Lume Orchestrator** — the single external
entry point and the agent that coordinates everything behind it. It is a design
doc, so it makes architecture-level decisions (the MCP surface, the state model,
the failure model). It does **not** contain implementation or production code,
per Phase 0 constraints.

It builds on the approved [requirements](requirements.md). Where the orchestrator's
MCP surface or coordination behaviour depends on an unproven assumption, it is
flagged **(pending WORK-0007)** — the MCP two-layer spike must confirm it before
Phase 1 build.

---

## 1. What the orchestrator is

The orchestrator is **not a router**. It is the agent that external clients talk
to over a single MCP connection, and it reasons about intent, coordinates the
capabilities that do the work, and tracks the state of multi-step workflows.

### Scope decision: general core, SDLC as the first instance

The orchestrator is designed as a **general, capability/template-aware
coordinator** — not an SDLC-specific one. The SDLC agents (coding, infra, work,
provisioning, obs) are simply its **first registered capabilities**.

**This generality lives at the contract level only.** Phase 0/1 implementation
wires up exactly the SDLC capabilities and nothing else. The general model must
not become a licence to build template/capability machinery before a second
template exists — that would violate the "do not build what you do not need yet"
must-not. General in *design*; SDLC-only in what is *built*.

### Decomposition is a capability, not the core

The orchestrator is a **thin, mostly-deterministic coordinator**. It does not hold
domain planning intelligence. Task decomposition is performed by a **planner
capability** that the orchestrator invokes — configurable per template. This keeps
the core domain-agnostic and keeps inference where it is genuinely needed (the
planner), honouring "deterministic over inference."

### Responsibilities

The orchestrator owns:

- **Intent intake** — receive an intent from any MCP client.
- **Planner invocation** — route the intent to the relevant template's planner
  capability, which returns a step plan.
- **Coordination** — drive each step by invoking the right capability with scoped,
  compressed context.
- **Validation-loop enforcement** — run the deterministic validation suite after
  each step (see §4); the LLM never decides success/failure/next action.
- **Workflow-state tracking** — persist and advance the state of every in-flight
  workflow (see §3).
- **Escalation** — apply the model-routing escalation chain on failure (see §5).
- **Approval gating** — pause and require human approval for high-blast-radius and
  (by default) irreversible actions; resume on decision.
- **Audit** — write an append-only, signed audit record for every action.

The orchestrator does **not**: perform domain work, plan within a domain, hold
durable state in-process, apply infrastructure directly, or infer control flow.

```
External clients (any MCP client)
  Claude Code · lume CLI · lume web · Lume itself
        │  one MCP connection (≤5 intent tools)
        ▼
  Lume Orchestrator  (thin · stateless · deterministic core)
   intent → planner capability → coordinate → validate → escalate → approve → audit
        │ internal (never MCP-exposed externally)
        ▼
  Capabilities (first instances = SDLC agents)
   planner · coding · infra · work · provisioning · obs · …
        │
  Durable state store  (swappable: embedded local ↔ enterprise datastore)
```

---

## 2. External MCP surface (5 tools, intent-based, client-agnostic)

Hard cap of 5 tools. The surface is intent-based: clients say *what* they want;
the orchestrator decides *how*. No internal/agent tools are ever exposed here.

Lifecycle (install/build/remove templates and capabilities) is **not** a separate
tool — it is carried as intents on `lume_task`, with discovery on `lume_query`.
A dedicated `lume_manage` tool is a **recorded future option**, triggered only if
external clients drive heavy template/capability lifecycle (see §6).

### `lume_task` — submit an intent

- **Purpose**: the one channel for "do something" — work *and* lifecycle intents
  ("add rate limiting to the gateway"; "install the research template"; "build a
  capability that reads my calendar").
- **Inputs**: `intent` (natural language); optional `context_refs`; optional
  `template_hint`; optional `dry_run`.
- **Outputs** (structured): `task_id`; `accepted` | `needs_clarification` |
  `rejected`; `plan_summary` (human-readable); `blast_radius`
  (none|low|medium|high); `pending_approval` (bool).

### `lume_query` — ask about state, knowledge, or capability

- **Purpose**: read-only questions, including **discovery** — "what can Lume do
  right now?", "what templates/capabilities are installed?", "what did task X
  change?". Returns **structured, typed** results (deterministic listing — never
  an inferred prose catalogue).
- **Inputs**: `query` (natural language or typed selector); optional `scope`
  (capabilities | templates | workflow | knowledge).
- **Outputs** (structured): typed result set matching the scope (e.g. capability
  descriptors, template descriptors, query answer with provenance).

### `lume_status` — progress of in-flight work

- **Purpose**: workflow progress for one or all tasks. Distinct from `lume_query`:
  status is live workflow telemetry, query is knowledge/discovery.
- **Inputs**: optional `task_id` (all in-flight if omitted).
- **Outputs** (structured): per task — `state` (planning|running|blocked|
  awaiting_approval|done|failed); `steps[]` with per-step state; `current_blast_
  radius`; `pending_approvals[]`; `last_audit_ref`.

### `lume_approve` — respond to an approval gate

- **Purpose**: the human (or a sufficiently-trusted identity) answers a pending
  approval, resuming or cancelling the gated step.
- **Inputs**: `approval_id`; `decision` (approve | reject); optional `reason`.
- **Outputs** (structured): `result` (resumed | cancelled); updated task `state`;
  `audit_ref`.

### `lume_context` — provide or manage context

- **Purpose**: give the orchestrator/capabilities scoped context (a repo, a
  document, a prior result) and manage its lifecycle. Compression/retrieval design
  belongs to WORK-0005; this tool is the external handle to it.
- **Inputs**: `operation` (add | update | remove); `payload` or `ref`; `scope`.
- **Outputs** (structured): `context_id`; `ack`; `summary` of what is now in scope.

---

## 3. State model

### Decision: stateless orchestrator over a swappable durable store

The orchestrator holds **no durable state in-process**. Every category of durable
state lives in a **pluggable state store behind a clean contract** — embedded and
local on a single desktop (e.g. a file/embedded DB), a scalable datastore at
enterprise scale, with the *same* orchestrator logic over both. This is the
**scale-agnostic** requirement expressed in the state design, and it gives crash
recovery and horizontal scale (any instance can resume any workflow).

The durability *mechanism* (event-sourcing vs snapshotting) is **deferred to
WORK-0005** and may warrant a spike. This document fixes only the *contract*: the
orchestrator is stateless logic over a swappable store.

### State the orchestrator owns

| State category | Contents | Lifetime |
|---|---|---|
| Workflow state | task, ordered steps, per-step status, current node | until task done/archived |
| Approvals | pending approval gates, decisions, reasons | until resolved, then audited |
| Audit log | append-only, signed record of every action | permanent (retention per WORK-0004) |
| Registry | installed capabilities and templates, versions | life of the instance |
| Identity/permission context | resolved per call, not durably owned here | transient (per request) |

Broad context-store design (compression, retrieval, local-vs-cloud tiering) is
**owned by WORK-0005** and only referenced here.

### How workflow state flows

1. Client calls `lume_task` → orchestrator **persists a new workflow record**
   (status `planning`) and returns `task_id`.
2. Orchestrator invokes the **planner capability**; the returned step plan is
   **written to the store** (status `running`).
3. For each step: orchestrator invokes the target capability with **scoped,
   compressed context** (token efficiency) → capability returns a **structured
   result** → orchestrator runs the **deterministic validation suite** → updates
   the step's state in the store.
4. On a gate: status `awaiting_approval`; the workflow is durable, so it waits
   without holding a process.
5. On completion: final result assembled, status `done`, audit finalised.

Because all state is in the store, a crashed or replaced orchestrator instance
**resumes from the last persisted step** — no in-flight work is lost.

---

## 4. Control loop (per step)

Restates the CLAUDE.md loop with the planner-capability decision applied:

```
[PLAN]     inference — the planner CAPABILITY decomposes intent into steps
[ACT]      deterministic — orchestrator invokes one capability via typed MCP tool
[VALIDATE] deterministic — validation suite returns a typed struct:
              done: bool            ← never inferred
              failures: Finding[]   ← never inferred
              next_action: enum     ← never inferred
[REFINE]   inference (on FAIL) — targeted prompt on the failures only
[ESCALATE] retries exhausted → larger local → cloud → human (see §5)
```

The orchestrator's core is deterministic end-to-end; inference appears only inside
the planner (PLAN) and refinement (REFINE) capabilities.

---

## 5. Failure model

The orchestrator distinguishes failure **classes**, because they warrant different
responses. Success/failure is always the deterministic VALIDATE output — never
inferred.

1. **Task-hard failure** — capability ran correctly but output failed validation
   (`done=false`). → REFINE on the failures, then ESCALATE per model routing:
   local ×2 → larger local → ×4 → cloud (one targeted call) → blocked.
2. **Contract violation** — capability returned malformed / wrong-schema output (a
   *capability bug*, not a hard task). → retry once; if it repeats, mark the
   capability **degraded** and surface — do not consume the escalation chain on a
   broken component.
3. **Timeout / unresponsive** — treat as transient: bounded retry with backoff;
   long-running capabilities report progress via heartbeat to distinguish "still
   working" from "stuck." Then escalate.
4. **Unavailable** — capability/agent down. The step is `blocked`; because state is
   durable (§3), the workflow **resumes from its checkpoint** when the capability
   returns, rather than restarting.
5. **Escalation exhausted** (or cloud unavailable) → **blocked work item, surfaced
   to the human, full history retained** (per CLAUDE.md).

### Partial workflow failure: halt-and-surface

When a step fails for good partway through a workflow, the orchestrator
**halts, preserves completed steps' effects, and surfaces a blocked work item**
with state intact for the operator to decide. This is safe because GitOps changes
are reconcilable and irreversible real-world actions are already human-gated — so
a dangerous partial state is rare by construction.

**Compensation/rollback** (capabilities define an "undo", orchestrator unwinds
completed steps) is a **recorded future option**, triggered only by capabilities
with non-reconcilable side effects (see §6).

### Cross-cutting: idempotency

Because the orchestrator is stateless over a durable store and resumes after
crashes, **every workflow step must be idempotent / safe to retry** — a
crash-and-resume must never double-apply an effect. This is a requirement on every
capability's MCP tools, recorded for the agent-boundary analysis (WORK-0003).

---

## 6. Known open questions / deferred

- **MCP surface validation** — the 5-tool intent surface and the two-layer
  coordination it implies are **pending WORK-0007** (MCP two-layer spike). The
  spike may force a change to inputs/outputs or tool count.
- **State store mechanism** — event-sourcing vs snapshotting, and the concrete
  local and enterprise store choices: **deferred to WORK-0005**.
- **`lume_manage` tool** — promote lifecycle to a dedicated tool *only if* external
  clients drive heavy template/capability lifecycle. Future option, not now.
- **Compensation/rollback** — add only when a capability has non-reconcilable side
  effects. Future option, not now.
- **Planner capability internals** — how the planner itself is built, prompted, and
  model-routed: deferred to the agent-boundary analysis (WORK-0003) and the
  validation-loop spike (WORK-0011).
- **Identity/permission resolution detail** — owned by WORK-0004 (security and auth).

---

## Sign-off

- [ ] **Neil has reviewed and explicitly approved this document.**
