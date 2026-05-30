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
behaviour depends on an unproven assumption, it is flagged **(pending WORK-0007)** —
the MCP two-layer spike must confirm it before Phase 1 build.

## Design general, build simple

The orchestrator is *designed* as a general, capability/template-aware coordinator
(the platform direction in the requirements). But **Phase 0/1 builds the simplest
SDLC-only realisation** of that design. Anything that only earns its keep once a
*second* template exists is marked **RESERVED — do not build yet**. This is the
"design general, build simple" rule, and it is how the platform vision and the
"do not build what you do not need yet" must-not are held at once.

Concretely, the **Phase 0/1 build** is:

- the planner runs **inline** in the orchestrator for the SDLC template (extracted
  to a swappable capability only when a second template lands);
- state persists to a single **embedded local store** directly behind the state
  contract (no multi-backend swap machinery yet);
- **no** template/capability registry, discovery, or lifecycle surface.

Each section below marks what is **build-now** vs **RESERVED**.

---

## 1. What the orchestrator is

The orchestrator is **not a router**. It is the agent that external clients talk
to over a single MCP connection, and it reasons about intent, coordinates the
capabilities that do the work, and tracks the state of multi-step workflows.

### Decomposition is a capability (RESERVED) — inline planner (build-now)

By design, task decomposition is a **planner capability** the orchestrator invokes,
configurable per template — keeping the core domain-agnostic and inference where it
is genuinely needed. **Build-now:** for the single SDLC template, the planner runs
**inline** in the orchestrator; the planner/core boundary is a documented seam, not
built machinery. It is extracted to a separate capability **(RESERVED)** when a
second template exists. WORK-0003 defines what crosses the seam (the step-plan
schema, the capability-routing table).

### Responsibilities

The orchestrator owns:

- **Intent intake** — receive an intent from any MCP client.
- **Planning** — produce a step plan (inline for SDLC; via planner capability when
  reserved generality is built).
- **Coordination** — drive each step by invoking the right capability with scoped,
  compressed context.
- **Validation-loop enforcement** — run the deterministic validation suite after
  each step (see §4); the LLM never decides success/failure/next action.
- **Workflow-state tracking** — persist and advance the state of every in-flight
  workflow, including a **write-ahead intent record per step** (see §3).
- **Escalation** — apply the model-routing escalation chain on failure (see §5).
- **Approval gating** — pause and require human approval for high-blast-radius and
  (by default) irreversible actions; resume on decision. The earned-autonomy
  mechanism that relaxes these gates is deferred (requirements §3; WORK-0015).
- **Audit** — write an append-only, signed audit record for every action.

The orchestrator does **not**: perform domain work, hold durable state in-process,
apply infrastructure directly, or infer control flow.

```
External clients (any MCP client)
  Claude Code · lume CLI · lume web · Lume itself
        │  one MCP connection (≤5 intent tools)
        ▼
  Lume Orchestrator  (thin · stateless · deterministic core)
   intent → plan → coordinate → validate → escalate → approve → audit
        │ internal (never MCP-exposed externally)
        ▼
  Capabilities (build-now = the SDLC agents)
   coding · infra · work · provisioning · obs   (planner inline for now)
        │
  Durable state store  (build-now: embedded local; multi-backend RESERVED)
```

---

## 2. External MCP surface (5 tools, intent-based, client-agnostic)

Hard cap of 5 tools. The surface is intent-based: clients say *what* they want; the
orchestrator decides *how*. No internal/agent tools are ever exposed here.

### Common outcome envelope (build-now)

Every tool returns a uniform, typed outcome so all clients branch the same way and
never parse prose:

- `outcome` — enum: `accepted` | `needs_clarification` | `rejected` | `error`.
- `reason_code` — machine-readable code (e.g. `permission_denied`, `unknown_intent`).
- `message` — human-readable detail.
- `clarification[]` — present only for `needs_clarification`: structured prompts.
- `surface_version` — semver of the MCP surface; additive-only within a major. A
  client reads this to negotiate compatibility.

### `lume_task` — submit an intent

- **Purpose**: the one channel for "do something". **Build-now:** SDLC work intents
  ("add rate limiting to the gateway"). **RESERVED:** lifecycle intents ("install
  the research template", "build a capability…") — designed for, not built, until a
  second template exists.
- **Inputs**: `intent` (natural language); optional `context_refs[]` (each a
  `context_id` from `lume_context`); optional `idempotency_key` (a client-supplied
  retry key — a repeated key returns the original `task_id`, never a duplicate
  workflow); optional `dry_run`. *(RESERVED: `template_hint` — omitted from the
  build-now contract; there is one template.)*
- **Outputs**: common envelope, plus `task_id`; `intent_kind` (`work` — RESERVED:
  `lifecycle`); structured `plan_ref`; `blast_radius` (none|low|medium|high);
  `pending_approval` (bool, authoritative for whether a gate will fire);
  `irreversible` (bool, advisory). `dry_run` returns the plan/blast fields **without**
  persisting a workflow or minting a durable `task_id`.

### `lume_query` — ask about state, knowledge, or change-set

- **Purpose**: read-only questions returning **structured, typed** results (never an
  inferred prose catalogue). **Build-now scopes:** `workflow` (any task by id,
  including completed/archived), `knowledge`, `audit` (resolve an `audit_ref` to a
  typed, signed record set — signing mechanics per WORK-0004). **RESERVED scopes:**
  `capabilities`, `templates` (discovery needs a registry — not built yet).
- **Inputs**: `query`; `scope`; list params `limit`, `cursor`, `filter`.
- **Outputs**: common envelope, plus a paginated list envelope — `items[]`,
  `next_cursor`, optional `total` — typed to the scope.

### `lume_status` — progress of in-flight work

- **Purpose**: live workflow telemetry. Boundary with `lume_query`: `lume_status`
  serves tasks **not yet archived**; `lume_query` scope=`workflow` serves any task by
  id including completed/archived and change-sets. Delivery model is **polling** for
  v1 (streaming RESERVED).
- **Inputs**: optional `task_id` (all in-flight if omitted); optional `since_token`
  for cheap re-polls.
- **Outputs**: common envelope, plus per task — `state` (planning|running|blocked|
  awaiting_approval|done|failed); `steps[]` with per-step `state` and `progress`;
  `current_blast_radius`; `pending_approvals[]` (each an **approval descriptor**, see
  below); `change_token`; `last_audit_ref`.

### `lume_approve` — respond to an approval gate

- **Purpose**: a human (or sufficiently-trusted identity) answers a pending approval,
  resuming or cancelling the gated step.
- **Approval descriptor** (minted when a gate fires; appears in `lume_status.
  pending_approvals[]`): `{approval_id, task_id, step_id, blast_radius, prompt,
  required_trust}` — this is how a client correlates an approval to its task and step.
- **Inputs**: `approval_id`; `decision` (approve | reject); optional `reason`;
  optional `idempotency_key`.
- **Outputs**: common envelope, plus `result` (resumed | cancelled); updated task
  `state`; `audit_ref`.

### `lume_context` — provide or manage context

- **Purpose**: give the orchestrator/capabilities scoped context and manage its
  lifecycle. Compression/retrieval design belongs to WORK-0005; this is the external
  handle to it.
- **Inputs**: `operation` (add | update | remove); `payload` or `ref`; `scope`.
- **Outputs**: common envelope, plus `context_id` (the token passed in
  `lume_task.context_refs`); `summary` of what is now in scope. remove/update on a
  missing or in-use `context_id` returns `error` with the appropriate `reason_code`.

---

## 3. State model

### Stateless orchestrator over a swappable store (build-now: embedded local)

The orchestrator holds **no durable state in-process**. State lives behind a clean
**state-store contract**. **Build-now:** a single **embedded local store** directly
behind that contract (e.g. a file/embedded DB) — no multi-backend swap machinery.
**RESERVED:** the scalable enterprise datastore, swapped in behind the same contract
when scale demands it. Same orchestrator logic over both. The contract is fixed here;
the durability *mechanism* (event-sourcing vs snapshotting) and concrete stores are
**deferred to WORK-0005**.

### State the orchestrator owns

| State category | Contents | Lifetime | Scope |
|---|---|---|---|
| Workflow state | task, steps, per-step status, **write-ahead step intents** | until done/archived | build-now |
| Approvals | pending gates, decisions, reasons | until resolved, then audited | build-now |
| Audit log | append-only, signed record of every action | permanent (WORK-0004) | build-now |
| Identity/permission | resolved per call, not durably owned here | transient | build-now |
| Registry | installed capabilities/templates, versions | life of instance | RESERVED |

Broad context-store design (compression, retrieval, local-vs-cloud tiering) is
**owned by WORK-0005**. WORK-0005 must also consider that categories have different
access shapes (high-write resume-critical workflow state vs read-mostly registry)
and may need distinct backing semantics behind the one contract — not one mechanism
assumed to fit all.

### How workflow state flows, and how resume stays safe

1. Client calls `lume_task` → orchestrator **persists a new workflow record**
   (status `planning`), returns `task_id`. An `idempotency_key` that has been seen
   returns the existing `task_id` instead of creating a duplicate.
2. Orchestrator plans (inline) → the step plan is **written to the store**
   (status `running`).
3. For each step: orchestrator **writes a step-intent record** to the store *before*
   acting, then invokes the capability with scoped, compressed context → capability
   returns a **structured result** → orchestrator runs the **deterministic validation
   suite** → records the step result.
4. On a gate: status `awaiting_approval`; the workflow is durable, so it waits
   without holding a process.
5. On completion: final result assembled, status `done`, audit finalised.

**Crash-safe resume.** Because every step writes its *intent* before acting, a
crashed or replaced orchestrator instance can, on resume, see "step N was attempted
but has no result" and decide safely — re-run if the capability tool is idempotent,
or **check-then-act** (query the external system: does the PR/branch already exist?)
for effects that are not naturally idempotent. This is the honest mechanism behind
"resume from the last step": it relies on write-ahead records in the *store*, not on
in-process state, and on capability tools being **idempotent or check-then-act
safe** — a hard requirement recorded for WORK-0003. Proving it for a non-idempotent
SDLC effect (PR creation) is an explicit goal of WORK-0007.

---

## 4. Control loop (per step)

```
[PLAN]     inference — decompose intent into steps (inline for SDLC; planner
                       capability when reserved generality is built)
[ACT]      deterministic — orchestrator invokes one capability via typed MCP tool
[VALIDATE] deterministic — validation suite returns a typed struct:
              done: bool            ← never inferred
              failures: Finding[]   ← never inferred
              next_action: enum     ← never inferred
[REFINE]   inference (on FAIL) — targeted prompt on the failures only
[ESCALATE] retries exhausted → larger local → cloud → human (see §5)
```

The orchestrator's core is deterministic end-to-end; inference appears only in
planning (PLAN) and refinement (REFINE).

---

## 5. Failure model

The orchestrator distinguishes failure **classes**, because they warrant different
responses. Success/failure is always the deterministic VALIDATE output — never
inferred.

1. **Task-hard failure** — capability ran correctly but output failed validation
   (`done=false`). → REFINE on the failures, then ESCALATE per model routing:
   **2 failures on the local model → larger local model; 4 cumulative local failures
   → one targeted cloud call; cloud fails/unavailable → blocked** (matches CLAUDE.md).
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

**Classes 1 vs 2 must be deterministically separable.** Schema-validity (class 2) is
checkable, but "schema-valid yet semantically wrong" (class 1) vs "schema-invalid
because the model failed" can blur for local models. WORK-0011 (validation-loop PoC)
must demonstrate VALIDATE can separate them on real local-model output, and define the
response when both hold.

### Partial workflow failure: halt-and-surface

When a step fails for good partway through a workflow, the orchestrator **halts,
preserves completed steps' effects, and surfaces a blocked work item** with state
intact for the operator to decide.

Honest scope of this choice: the SDLC template *does* produce partial effects that
are **not** GitOps-reconcilable and **not** human-gated — a pushed branch, an opened
PR, a posted work-item update, a triggered CI run. Halt-and-surface **deliberately
leaves these for the operator to clean up**, rather than auto-undoing them. That is
acceptable for Phase 0/1 because such effects are **visible and non-destructive** (a
dangling PR is not data loss or spend) and the operator is in the loop — *not*
because partial state is rare. The blocked-work-item surface must therefore **list
the partial effects already applied** (e.g. "branch X pushed, PR #N opened") so the
operator can act.

**Compensation/rollback** (capabilities define an "undo", orchestrator unwinds) is a
**RESERVED future option**, triggered when a capability gains a **destructive or
non-visible** side effect (deleting data, spending money) that halt-and-surface
cannot safely leave dangling.

---

## 6. Known open questions / deferred

- **MCP surface validation (WORK-0007)** — the spike must exercise: `lume_task` with
  work intents (and the reserved lifecycle path) confirming the common envelope and
  `intent_kind` serve a real client without a union explosion; the error/rejection
  shapes; a **mid-workflow failure after a real push/PR** (validates §5 halt scope);
  and **crash-safety of a non-idempotent effect** (PR creation) under the store's
  resume semantics (validates §3).
- **Class 1 vs 2 discrimination (WORK-0011)** — prove VALIDATE separates
  schema-invalid from schema-valid-but-wrong on real local output.
- **State store mechanism (WORK-0005)** — event-sourcing vs snapshotting; per-category
  backing semantics; concrete local and enterprise stores; latency of the
  persist-per-step path on the embedded store must not regress the solo-desktop feel.
- **Capability idempotency / check-then-act (WORK-0003)** — a hard requirement on
  every capability's MCP tools; the agent-boundary analysis must validate each SDLC
  capability can meet it.
- **RESERVED generality** — planner-as-capability, the multi-backend store swap,
  template/capability registry, discovery, and lifecycle (`lume_manage`, lifecycle
  intents, `template_hint`): designed-for, built only when a second template exists.
- **Earned-autonomy gate relaxation** — mechanism deferred (requirements §3; WORK-0015).
- **Identity/permission resolution detail** — owned by WORK-0004.

---

## Sign-off

- [ ] **Neil has reviewed and explicitly approved this document.**
