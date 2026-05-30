# Lume — Agent Boundary Analysis

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0003

---

This document defines the five internal SDLC agents — the **first registered
capabilities** of the orchestrator (see [orchestrator design](orchestrator-design.md)).
For each: responsibilities, MCP tools (name + purpose), validation suite, and
escalation chain. It then **explicitly verifies no overlapping responsibilities**.

It is a design doc; no production code, per Phase 0. Model assignments are
provisional pending the local-model evaluation (WORK-0010); the store/idempotency
mechanics are pending WORK-0007/WORK-0005.

## Scope: capabilities, not a fixed agent set

Per the orchestrator design, these five are the SDLC template's capabilities. The
"agent" framing is build-now; the general capability/template model is RESERVED. The
planner is **not** a sixth agent here — it runs inline in the orchestrator for the
SDLC template (build-now).

## Cross-cutting contract (applies to every agent below)

Routed here from the orchestrator design — binding on **every** agent's MCP tools:

- **Typed result.** Every tool returns the deterministic validation struct
  (`done: bool`, `failures: Finding[]`, `next_action: enum` — never inferred) **plus**
  `applied_effects[]` (each effect's `type`, external `id`, `reversible` flag),
  reported by the agent, never inferred by the orchestrator.
- **Idempotency / check-then-act.** Every tool must be idempotent or check-then-act
  safe. A tool with a non-idempotent external effect (e.g. opening a PR, creating a
  repo) must let the orchestrator record the **deterministic external identity** (e.g.
  computed branch name) before acting, so a crash-resume can detect "already done."
- **Loop + escalation.** Every action runs through the orchestrator's loop (PLAN ·
  ACT · VALIDATE · REFINE · ESCALATE). The escalation chain is uniform: local model
  ×2 → larger local → ×4 cumulative → one targeted cloud call → blocked work item to
  the human. Per-agent rows below name only the *model class*; final model
  assignments are WORK-0010.

---

## 1. Coding Agent

- **Responsibility.** Write and modify **application source code** within a repo:
  implement features and fixes, refactor, run and interpret tests. Owns code, nothing
  else.
- **MCP tools.**
  - `read_files` — read repo files into scoped context.
  - `apply_patch` — write/modify source files (idempotent: same patch re-applies cleanly).
  - `run_tests` — execute the test suite; returns structured pass/fail.
  - `run_checks` — lint, typecheck, build; structured results.
  - `search_code` — typed code search.
  - `open_pr` — open a PR (non-idempotent → records deterministic branch/PR identity;
    check-then-act on resume).
- **Validation suite.** Tests pass, lint clean, typecheck clean, build succeeds — all
  deterministic; `done` is the conjunction, `failures` lists the specific failing
  check, `next_action` follows from them.
- **Escalation.** Code-generation model class (local coder → larger local coder →
  cloud reasoning → human).

## 2. Infra Agent

- **Responsibility.** Manage **existing** infrastructure: mutate existing resources'
  GitOps config (scale, tune, restart-via-config) and diagnose using Obs signals.
  Does **not** create new resources, own observability, or touch app code.
- **MCP tools.**
  - `edit_gitops_config` — mutate an **existing** resource's manifest in Git (writes
    to Git; never applies directly). Idempotent: desired-state edits converge.
  - `query_cluster_state` — read live cluster/resource state.
  - `diagnose` — read Obs signals + cluster state to localise a problem (read-only).
- **Validation suite.** Edited config is schema/policy-valid; the GitOps operator
  reconciles it; the queried live state reaches the desired state. Deterministic
  checks; no inferred success.
- **Escalation.** Reasoning model class for diagnosis; deterministic for the edit.

## 3. Work Agent

- **Responsibility.** Manage **durable work items**: create/update/transition work
  items, backlog, status, and dependencies (the `.work/` + issue-tracker domain). Owns
  work-item state at rest. Does **not** run live workflow execution (that is the
  orchestrator) or do domain work.
- **MCP tools.**
  - `create_work_item` — create a work item (idempotent via client key).
  - `update_work_item` — update fields/status (idempotent).
  - `transition_status` — move an item through its lifecycle; rejects illegal
    transitions deterministically.
  - `query_work_items` — typed query over the backlog.
- **Validation suite.** Schema-valid item; legal state transition; no orphaned or
  cyclic dependencies. Fully deterministic.
- **Escalation.** Mostly deterministic; light classification (e.g. change-class
  inference) escalates rarely — router model class.

## 4. Provisioning Agent

- **Responsibility.** Create **new** things by writing declarative config to Git: new
  repos, tenants, GitOps config for **new** resources, Crossplane claims, bootstrap
  projects. Never mutates existing resources (that is Infra), never writes app code.
- **MCP tools** (all write to Git, never apply directly; from CLAUDE.md).
  - `provision_repo` — create a new repo (non-idempotent → records repo identity;
    check-then-act).
  - `provision_tenant` — create a new tenant's config.
  - `write_gitops_config` — write GitOps config for a **new** resource.
  - `write_crossplane_claim` — write a new Crossplane claim.
  - `bootstrap_lume_project` — scaffold a new Lume-managed project (repo skeleton,
    config, CLAUDE.md, hedl setup — detailed in WORK-0012/WORK-0013).
- **Validation suite.** Generated config is schema/policy-valid; the artifact exists
  in Git; the GitOps operator picks it up. Deterministic.
- **Escalation.** Reasoning model class for scaffolding decisions; deterministic for
  the writes.

## 5. Obs Agent

- **Responsibility.** Own the **observability plane**: instrument, collect, store, and
  query metrics/logs/traces; own alerting and dashboards as its declarative-config
  domain. Produces the signals Infra and the orchestrator consume. Does **not** act on
  infrastructure (that is Infra) or write app code.
- **MCP tools.**
  - `query_metrics`, `query_logs`, `query_traces` — typed reads over telemetry.
  - `get_health` — structured health/SLO snapshot for a target.
  - `define_alert` — write/manage an alert rule or dashboard (Obs's own
    declarative-config domain in Git; idempotent desired-state).
- **Validation suite.** Queries return well-typed data; alert/dashboard config is
  schema-valid; signal freshness within bounds. Deterministic.
- **Escalation.** Mostly deterministic queries; anomaly summarisation (if any) uses a
  reasoning model class.

---

## 6. No-overlap verification

Each agent owns a disjoint domain. The boundaries that were genuine collisions are
resolved explicitly:

- **Provisioning vs Infra** — *create vs mutate*: Provisioning writes config for
  *new* resources; Infra edits *existing* resources' config. Disjoint targets.
- **Obs vs Infra ("observe")** — *signal vs action*: Obs owns the observability plane
  and produces signals; Infra consumes them to act. "Observe" is not Infra's.
- **Work vs orchestrator** — *at-rest vs in-flight*: the Work agent owns durable work
  items; the orchestrator owns live workflow execution state.
- **Coding vs Provisioning** — *code vs skeleton*: Provisioning writes the repo/config
  skeleton; Coding writes and modifies application code.
- **Obs config vs infra config** — *domain-scoped*: alert/dashboard config is Obs's
  domain; resource config is Infra (mutate) / Provisioning (create).

Domain summary — each owns exactly one column, no cell shared:

| Agent | Owns | Writes to Git? | Never does |
|---|---|---|---|
| Coding | application code + tests | only `open_pr` (branch/PR) | infra, provisioning, work-items |
| Infra | existing-resource config + diagnosis | mutate existing manifests | create resources, observability, code |
| Work | durable work items | work-item store | live execution, domain work |
| Provisioning | new resources/repos/tenants | create new config | mutate existing, app code |
| Obs | observability plane + alert/dashboard config | obs-domain config only | act on infra, code |

No responsibility appears in two rows. The acceptance-criterion overlap check passes.

---

## 7. Known open questions / deferred

- **Model assignments (WORK-0010)** — each agent's concrete local/cloud models and
  pass/latency thresholds come from the local-model evaluation; rows above name only
  the model *class*.
- **Validation-suite internals (WORK-0011)** — the deterministic VALIDATE that
  produces `done/failures/next_action` (incl. class 1 vs 2 separation) is proven by
  the validation-loop PoC.
- **Tool result + idempotency contract (this doc + WORK-0007)** — `applied_effects[]`
  and check-then-act identities are specified here; crash-safety of non-idempotent
  effects (PR/repo creation) is proven by WORK-0007.
- **Provisioning scaffold detail (WORK-0012/WORK-0013)** — `bootstrap_lume_project`
  and the project template are designed in the provisioning-agent and
  project-template work items.
- **Identity/permissions per tool (WORK-0004)** — each tool's required trust level and
  blast radius come from the security/auth requirements.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the
operator's review-and-merge is the approval gate (per the `/iterate` flow). There is
no separate in-file approval step; an unmerged PR means not-yet-approved.
