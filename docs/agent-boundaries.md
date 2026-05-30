# Lume — Agent Boundary Analysis

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0003

---

This document defines the five internal SDLC capabilities — the **first registered
capabilities** of the orchestrator (see [orchestrator design](orchestrator-design.md)).
For each: responsibilities, MCP tools (name + purpose), validation suite, and
escalation chain. It then **explicitly verifies no overlapping responsibilities**.

It is a design doc; no production code, per Phase 0. Model assignments are
provisional pending WORK-0010; store/idempotency mechanics pending WORK-0007/0005.

## Scope and classification

Per the orchestrator design, these five are the SDLC template's capabilities. The
"agent" framing is build-now; the general capability/template model is RESERVED. The
planner runs inline in the orchestrator (not a sixth capability here).

The partition axis is **artifact class** — each capability owns a disjoint class of
artifact (or work). Ownership of any Git artifact is decided by its **resource kind /
reconciling controller**, not its file location; a file mixing kinds is split into
per-kind artifacts. This axis is robust to GitOps desired-state (it never asks an
agent to pre-classify a write as "create" vs "mutate") and gives every create, change,
and **delete** a single owner.

**Inference vs deterministic.** Coding, Infra, Provisioning, and Obs are inference
capabilities (they run the orchestrator's PLAN/ACT/VALIDATE/REFINE/ESCALATE loop). The
**Work agent is a deterministic service** — it performs no inference (Principle 1), so
the orchestrator calls its typed tools directly without a PLAN/REFINE loop. (This
nuances CLAUDE.md's flat "5 agents" framing; reconciliation is tracked in WORK-0015.)

## Cross-cutting contract (applies to every capability below)

Routed here from the orchestrator design — binding on **every** capability's MCP tools:

- **Typed result.** Every tool returns the deterministic validation struct
  (`done: bool`, `failures: Finding[]`, `next_action: enum` — never inferred) **plus**
  `applied_effects[]` (each effect's `type`, external `id`, `reversible` flag),
  reported by the capability, never inferred by the orchestrator.
- **Idempotency / check-then-act.** Every tool must be idempotent or check-then-act
  safe; a tool with a non-idempotent external effect lets the orchestrator record the
  deterministic external identity before acting, so a crash-resume detects "already
  done" (orchestrator design §3).
- **The orchestrator owns the change-set.** Capabilities write files to the
  orchestrator-managed working branch; **the orchestrator opens and updates one PR per
  workflow** (recording the branch/PR identity). No capability opens its own PR — this
  is why a single workflow that touches several artifact classes still lands as one
  coherent PR.
- **Loop + escalation.** The escalation chain is uniform (orchestrator design §5):
  **2 failures on the local model → larger local model; 4 cumulative local failures →
  one targeted cloud call; cloud fails/unavailable → blocked work item to the human.**
  Rows below name only the *model class*; final assignments are WORK-0010.

---

## 1. Coding Agent

- **Owns artifact class:** application source code.
- **Responsibility.** Write and modify application source within a repo: implement
  features and fixes, refactor, run and interpret tests. Owns code, nothing else — it
  does not open PRs (the orchestrator does) and does not write manifests/config.
- **MCP tools.**
  - `read_files` — read repo files into scoped context.
  - `apply_patch` — write/modify source files on the working branch (idempotent: same
    patch re-applies cleanly).
  - `run_tests` — execute the test suite; structured pass/fail.
  - `run_checks` — lint, typecheck, build; structured results.
  - `search_code` — typed code search.
- **Validation suite.** Tests pass, lint clean, typecheck clean, build succeeds — all
  deterministic; `done` is their conjunction, `failures` names the failing check,
  `next_action` follows.
- **Escalation.** Code-generation model class.

## 2. Infra Agent

- **Owns artifact class:** in-cluster workload manifests (Deployments, Services, HPAs,
  Gateways, network/rate-limit policies, etc.) — every change to them: **create,
  scale, mutate, and delete**.
- **Responsibility.** Manage running workloads via their GitOps manifests, and
  diagnose problems by consuming Obs's typed output. Does not own lifecycle/infra
  artifacts (Provisioning), observability artifacts (Obs), or app code.
- **MCP tools.**
  - `write_workload_manifest` — create/edit a workload manifest on the working branch
    (writes to Git; never applies directly; idempotent desired-state).
  - `delete_workload_manifest` — remove a workload manifest (high blast radius →
    human approval).
  - `query_cluster_state` — read live cluster/resource state.
  - `diagnose` — consume Obs's typed signals + cluster state to localise a problem and
    form a root-cause hypothesis (the inference). Does not re-query raw telemetry —
    it takes Obs output as input.
- **Validation suite.** Manifest is schema/policy-valid; the GitOps operator
  reconciles it; queried live state reaches desired state. Deterministic.
- **Escalation.** Reasoning model class for diagnosis; deterministic for the write.

## 3. Work Agent (deterministic service)

- **Owns artifact class:** durable work items (backlog, status, dependencies — the
  `.work/`/issue-tracker domain). Owns work-item state **at rest**.
- **Responsibility.** Store and transition work items. Performs no inference, so it
  runs no PLAN/REFINE loop — the orchestrator calls its typed tools directly. Does not
  run live workflow execution (orchestrator) or domain work.
- **Status during execution.** A running item's status is written by the
  **orchestrator** as the sole writer, by calling `transition_status`; the orchestrator
  maps its workflow-state enum (planning|running|blocked|awaiting_approval|done|failed)
  onto the work item's status. The Work agent never independently advances a status
  mid-flight, so there is no dual writer.
- **MCP tools.** `create_work_item`, `update_work_item`, `transition_status` (rejects
  illegal transitions deterministically), `query_work_items`.
- **Validation suite.** Schema-valid item; legal transition; no orphaned/cyclic deps.
  Fully deterministic.
- **Escalation.** None — deterministic service; no model class.

## 4. Provisioning Agent

- **Owns artifact class:** lifecycle / infrastructure artifacts — new repos, tenants,
  Crossplane infrastructure claims, and project scaffold. Owns these create → mutate →
  **delete** (e.g. resizing or tearing down a Crossplane claim). Never writes workload
  manifests (Infra), observability artifacts (Obs), or app code.
- **MCP tools** (all write to Git, never apply directly; from CLAUDE.md).
  - `provision_repo` — create a new repo (records repo identity; check-then-act).
  - `provision_tenant` — create a new tenant's config.
  - `write_crossplane_claim` — create/mutate a Crossplane infrastructure claim.
  - `delete_provisioned_artifact` — remove a repo/tenant/claim (high blast radius →
    human approval).
  - `bootstrap_lume_project` — scaffold a new project's container: repo skeleton,
    config, CLAUDE.md, CI, hedl setup (detail in WORK-0012/0013). The scaffold is
    **non-application files only**; any starter application source is Coding's first
    commit.
- **Validation suite.** Generated artifact is schema/policy-valid; it exists in Git;
  the operator picks it up. Deterministic.
- **Escalation.** Reasoning model class for scaffolding; deterministic for the writes.

> Note: `write_gitops_config` from CLAUDE.md's provisional list is **split by artifact
> class** — workload manifests are Infra's `write_workload_manifest`; new-resource
> infra claims are Provisioning's `write_crossplane_claim`. (Tracked for the CLAUDE.md
> reconciliation, WORK-0015.)

## 5. Obs Agent

- **Owns artifact class:** the observability plane and its artifacts — metrics/logs/
  traces collection and query, plus alert rules and dashboards (by resource kind, e.g.
  PrometheusRule, ServiceMonitor, dashboards). Produces the signals Infra and the
  orchestrator consume. Does not act on infrastructure (Infra) or write app code.
- **MCP tools.**
  - `query_metrics`, `query_logs`, `query_traces` — typed reads over telemetry.
  - `get_health` — structured health/SLO snapshot for a target (raw/structured signal,
    not a diagnosis — diagnosis is Infra's `diagnose`).
  - `write_obs_artifact` — create/edit/delete an alert rule or dashboard (Obs's
    artifact class in Git; idempotent desired-state).
- **Validation suite.** Queries return well-typed data; obs artifact is schema-valid;
  signal freshness within bounds. Deterministic.
- **Escalation.** Mostly deterministic; anomaly summarisation (if any) uses a reasoning
  model class.
- **Auto-remediation is RESERVED.** In Phase 0/1, Obs signals are **advisory to the
  human** — there is no closed-loop "Obs fires → Infra acts" trigger. A signal becomes
  action only via a human/operator-initiated intent. The signal→action trigger path is
  designed only when a use-case needs it (see §7).

---

## 6. No-overlap verification

Artifact class is the single partition axis; each capability owns exactly one class,
classified by resource kind / reconciling controller.

- **Coding** — application source code.
- **Infra** — in-cluster workload manifests (create/scale/mutate/delete).
- **Work** — durable work items.
- **Provisioning** — lifecycle/infra artifacts: repos, tenants, Crossplane claims,
  project scaffold (create/mutate/delete).
- **Obs** — observability artifacts: telemetry, alert rules, dashboards.

Resolved collisions:

- **Provisioning vs Infra** — *artifact class, not create-vs-mutate*: Infra owns
  workload manifests (any change incl. create and delete); Provisioning owns
  repos/tenants/Crossplane-claims/scaffold. The headline `add rate limiting` change
  (new policy + gateway edit) is **all workload manifests → Infra**, one capability,
  one PR.
- **Obs vs Infra** — *signal vs action*: Obs produces signals and owns obs artifacts;
  Infra consumes Obs's typed output to act. "Observe" is not Infra's. (This revises
  CLAUDE.md's "Infra: scale, debug, observe" — tracked in WORK-0015.)
- **Work vs orchestrator** — *store vs writer*: Work stores work items; the
  orchestrator is the sole writer of a work item's status during execution.
- **Coding vs Provisioning** — *source vs scaffold*: scaffold is non-application files;
  starter source is Coding's first commit.
- **diagnose vs get_health** — Obs returns signals/health snapshots; Infra's `diagnose`
  consumes that typed output and adds the cluster-state correlation + root-cause
  hypothesis. Infra does not re-query raw telemetry.
- **DELETE** — owned by the artifact's class owner (Infra deletes workload manifests;
  Provisioning deletes repos/tenants/claims; Obs deletes obs artifacts). High blast
  radius → human approval.
- **PR/branch ownership** — the orchestrator owns the per-workflow branch and PR; no
  capability opens its own, so a multi-class workflow still yields one PR.

No artifact class or responsibility appears under two capabilities. The
acceptance-criterion overlap check passes.

---

## 7. Known open questions / deferred

- **Model assignments (WORK-0010)** — concrete models and pass/latency thresholds per
  capability; rows name only the model class.
- **Validation-suite internals (WORK-0011)** — the deterministic VALIDATE producing
  `done/failures/next_action` (incl. class 1 vs 2 separation).
- **Idempotency crash-safety (WORK-0007)** — proof for non-idempotent effects (PR/repo
  creation) under the store's resume semantics.
- **Auto-remediation trigger (RESERVED)** — the closed-loop signal→action path (Obs
  fires → a workflow acts) is designed only when a use-case needs it; Phase 0/1 signals
  are advisory-to-human.
- **Provisioning scaffold detail (WORK-0012/0013)** — `bootstrap_lume_project` content
  and the project template.
- **Identity/permissions per tool (WORK-0004)** — required trust level and blast radius
  per tool (e.g. the delete tools above).
- **CLAUDE.md reconciliation (WORK-0015)** — "observe→Obs", `write_gitops_config` split
  by artifact class, and Work-as-deterministic-service vs the flat "5 agents" framing.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
