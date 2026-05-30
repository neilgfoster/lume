# Lume — CLI and Self-Building Requirements

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0006

---

The `lume` CLI command surface, approval-gate requirements, rollback requirements, and
the safety constraints on Lume modifying itself. Builds on the approved
[orchestrator design](orchestrator-design.md) (the CLI is a client of its 5 MCP tools),
[security requirements](security-requirements.md) (approval/blast-radius/grants), and the
GitOps-everything principle (rollback). Requirements-level; no production code.

## 1. CLI command surface

The CLI is **intent-first**: the primary form is a bare intent; everything else is a thin
verb wrapping one of the orchestrator's 5 MCP tools. The user says *what* they want and
never thinks about agents, models, or tools. A richer command tree (e.g.
`lume agents`, `lume template …`) is **RESERVED** — not built in Phase 0/1.

- **`lume "<intent>"`** → `lume_task`. The headline command.
  - *Intent:* do something (work or, RESERVED, lifecycle) — e.g. add a feature, fix a bug.
  - *Inputs:* the intent string; optional `--context <id>…`, `--dry-run`, `--idempotency-key`.
  - *Outputs:* `task_id`, a human plan summary, `blast_radius`, and whether an approval is
    pending. Structured `--json` for non-human clients.
  - *Example:* `lume "add rate limiting to the API gateway"`
- **`lume status [<task_id>]`** → `lume_status`.
  - *Intent:* see progress of in-flight work.
  - *Inputs:* optional `task_id` (all in-flight if omitted); `--since <token>`.
  - *Outputs:* per task — state, per-step state/progress, current blast radius, **pending
    approvals** (with their `approval_id`), last audit ref.
  - *Example:* `lume status` · `lume status t_8f3a`
- **`lume approve <approval_id>`** → `lume_approve`.
  - *Intent:* answer a pending approval gate.
  - *Inputs:* `approval_id`; `--reject`; optional `--reason "<text>"`.
  - *Outputs:* resumed | cancelled; updated task state; audit ref.
  - *Example:* `lume approve a_22c1 --reason "looks right"`
- **`lume ask "<query>"`** → `lume_query`.
  - *Intent:* ask about state, knowledge, or what Lume can do (structured discovery).
  - *Inputs:* the query; optional `--scope workflow|knowledge|audit`; list params.
  - *Outputs:* a typed, paginated result set.
  - *Example:* `lume ask "what changed in task t_8f3a?"`
- **`lume context add|update|remove …`** → `lume_context`.
  - *Intent:* provide or manage scoped context.
  - *Inputs:* operation; a payload or ref; `--scope` (the value set is defined with the
    context-store design, WORK-0005); `remove` takes a `context_id`.
  - *Outputs:* `context_id`; a summary of what is now in scope, **including the
    confidentiality label assigned at ingestion** (security §1) so the operator sees it.
  - *Example:* `lume context add ./design-notes.md`
- **`lume undo <task_id>`** → a revert intent (see §3). Not a 6th MCP tool — sugar for a
  `lume_task` revert intent.
  - *Intent:* roll back what a task changed.
  - *Inputs:* `task_id`; `--dry-run`.
  - *Outputs:* a new task that reverts all Git-expressed effects and **reports the
    irreversible effects it could not undo** (rather than silently partial-reverting); its
    plan/blast radius.
  - *Example:* `lume undo t_8f3a`

All commands run under a resolved identity (CLI invocations are typically the `human`
identity) and pass through the full security pipeline (WORK-0004 §1).

## 2. Approval-gate requirements

Which actions require human approval, and why — enforced deterministically (WORK-0004
§3), surfaced via `lume status`, answered via `lume approve`.

- **High-blast-radius and irreversible actions** — human approval **by default** (delete,
  cloud spend, external comms, deploy). Why: blast radius + irreversibility (security §3).
- **Grant-pre-authorised classes** — an action covered by an active grant proceeds
  without a fresh approval (earned autonomy; security §2). The grant itself was
  human-issued and is scoped/expiring/audited.
- **Issuing or widening a grant** — always human (a high-blast action; security §2).
- **Constitutional-core changes** — **always human, no exceptions, never grant-relaxable**
  (see §4). This is the one class earned autonomy can never reach. This carve-out must be
  **encoded in the approval policy itself** — security §3's general "a grant may
  pre-authorise high-blast" rule must explicitly except the core-touching class (else the
  exception is only held across docs, not enforced). Routed to WORK-0004 / the security
  spike.
- **Low/medium, in-scope** — proceed under policy; surfaced in `lume status` and audited,
  not gated.

The CLI never lets an agent self-approve: `claude-code` and `lume-agent-*` identities
cannot approve; only `human` (or a matching grant) clears a gate.

## 3. Rollback requirements

Rollback rests on **GitOps**: Lume's changes are declarative config/code in Git, so
reverting is reverting Git and letting the operators reconcile.

- **What can be rolled back:**
  - **Anything expressed in Git** (workload manifests, claims, app code, config) — revert
    the commit; the GitOps operator reconciles the cluster back to the prior desired
    state. This includes **Lume's changes to itself** (they are Git commits).
  - **Workflow/work-item state** — superseded by a corrective task; the event log retains
    history.
  - **Cannot be rolled back:** **irreversible real-world effects** already applied —
    sent communications, external spend, a triggered external job. These are human-gated
    *precisely because* they cannot be undone; rollback reverts the config, not the
    side effect.
- **How:** `lume undo <task_id>` issues a **revert intent** → the orchestrator writes the
  revert to Git (a normal, audited, blast-classified action) → operators reconcile. Undo
  is itself a task (planned, validated, gated), not a privileged escape hatch.
- **Window:** anything in Git is revertible **for as long as history is retained**
  (effectively unbounded). The caveat is *stacked* changes: reverting an old change under
  newer dependent ones may break them. Because undo is a normal task, it runs the **full
  pipeline including VALIDATE on the reverted state** — so a revert that applies cleanly
  textually but breaks a dependent change is caught by validation (a task failure for the
  operator), not silently shipped. Textual merge conflicts surface the same way; neither
  is ever force-applied.

## 4. Self-modification safety

Lume building and fixing itself is the autonomy arc — but it must never be able to weaken
its own safety. Two tiers:

### Tier 1 — general self-improvement (same pipeline as any change)

Lume's changes to its own features, agents, capabilities, and templates go through the
**identical** SDLC: PLAN → ACT → VALIDATE → adversarial review → approval, written to Git
as a normal change. Specifically:

- No agent can self-approve its own change (`claude-code`/`lume-agent-*` cannot approve;
  WORK-0004 §2). A human (or a matching grant) gates the merge.
- Self-modifying changes are **high-blast by default** (they alter the running system).
- Rolled back like any change (§3) — they are Git commits.

Under earned autonomy, *these* classes can graduate to grant-pre-authorised over time —
subject to the Tier-2 interim block: **not** until the protected-core boundary is drawn.

### Tier 2 — the constitutional core (never autonomously modifiable)

A defined **protected core** is **always human-gated, can never be relaxed by a grant,
and is never autonomously self-modifiable regardless of Lume's trust level.** Only a
human can change it. **Conceptually**, the core comprises: the **security pipeline**
(`identity → permission → blast-radius → validation → execution → audit`); the
**blast-radius classification and approval logic**; the **audit chain and its signing**;
the **earned-autonomy grant mechanism itself**; and **this protected-core definition**
(so the boundary cannot be autonomously widened). The *precise* file/config/logic
enumeration is deferred to a governance work item (§5).

**Operational meaning of "non-self-modifiable":** a change recognised as core-touching
requires a **fresh `human`-trust approval bound to that specific change** — no grant, no
idempotency key, no cached prior approval can satisfy it (this is stronger than an
ordinary high-blast gate, which a grant may pre-authorise).

**Interim safe default (until the boundary is drawn):** every change to the `lume/`
orchestration repo (Lume modifying itself) — **and** to constitutional-core policy/config
wherever it lives (e.g. the OPA blast/approval/grant policy and audit-key config, which
may sit in the `config/` GitOps repo, not `lume/`) — is treated as **core-touching**:
non-grantable and human-gated. The boundary is deliberately over-approximated until
WORK-0014 draws the precise one (and confirms where core policy resides); **no Tier-1
self-modification class may graduate to grant-pre-authorised until that boundary exists.**

Why this tier exists: without it, the earned-autonomy model is self-referentially unsafe
— a sufficiently-trusted Lume could grant itself the right to relax its own guardrails. A
system that can earn the ability to disable its own safety is not safe.

**Enforcement** is by identity + policy: the policy must **reject grant issuance** for the
core-touching class unconditionally (not merely not offer it) and require a fresh human
approval — the concrete mechanism is specified by the security spike (WORK-0004 §6).

**Reconciliation with the autonomy arc:** this Tier deliberately **bounds** CLAUDE.md's
Phase-5 "Lume … ships autonomously" — autonomy is unbounded *outside* the core, never
*over* it. Note that the core's "no exceptions" is a **deliberately permanent** absolute:
the WORK-0015 reconciliation that demotes the general high-blast "no exceptions" to a
default **must preserve** this narrower one. Self-building still delivers the vision —
Lume freely improves everything outside the core under Tier 1.

---

## 5. Known open questions / deferred

- **Exact protected-core boundary** — the precise enumeration of files/config/logic that
  constitute the constitutional core needs a careful, reviewed definition before Lume does
  any autonomous self-modification. Recommend a dedicated governance work item (raise with
  the plan, WORK-0014). **Interim (§4):** all `lume/`-repo changes are treated as
  core-touching (non-grantable + human-gated), and no Tier-1 class graduates to a grant
  until the boundary is drawn.
- **Non-grantable enforcement** — the policy mechanism that makes the core-touching class
  un-grantable (security §3's approval rule must except it) is a named deliverable for
  WORK-0004 / the security spike.
- **Enforcement mechanism** — how "non-grantable" and "non-self-modifiable" are
  technically enforced (identity + OPA policy + which paths are protected) → the
  security stack (WORK-0004 / the recommended security spike).
- **Undo of stacked/dependent changes** — conflict-resolution UX for `lume undo` when
  newer changes depend on the reverted one.
- **Rollback of partial non-GitOps effects** — ties to the orchestrator's halt-and-surface
  (WORK-0002 §5): operator-driven cleanup of a pushed branch / open PR.
- **Earned-autonomy graduation** — which Tier-1 self-modification classes graduate, and on
  what evidence, depends on the deferred grant mechanism (requirements §3; WORK-0015).

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
