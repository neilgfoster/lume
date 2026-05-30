# Lume — Security and Auth Requirements

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0004

---

Security requirements for Lume: the threat model, identity model, blast-radius
controls, audit requirements, and a build-vs-adopt decision per capability. It builds
on the approved [requirements](requirements.md), [orchestrator design](orchestrator-design.md),
and [agent boundaries](agent-boundaries.md).

It is a design doc; no production code, per Phase 0. Adoption decisions are
**pending a security-stack spike** (see §6) — Phase 0 evaluates, it does not install.

## Guiding stance

- **Adopt the primitives, build only the glue and the AI-native defences.** Identity,
  policy, signing, and telemetry are solved problems — adopt strong OSS. Build only
  the Lume-specific pipeline glue and the defences unique to an agentic system
  (prompt-injection handling, capability provenance). This is the "do not build what
  others do much better" must-not applied to security.
- **The 6-step pipeline is the spine.** Every MCP tool call passes through:
  `identity resolution → permission check → blast-radius classification → validation →
  execution → audit`. Each section below maps to a step.
- **Deterministic security.** Identity, permission, blast-radius, and audit are
  deterministic; the LLM never decides any of them (Principle 1).

---

## 1. Threat model

### Trust boundaries

- **External client ↔ orchestrator** — the single MCP entry point; the only externally
  reachable surface. All external trust is established here.
- **Orchestrator ↔ capability** — internal MCP; capabilities are never externally
  reachable and act only under a resolved identity + scoped permissions.
- **Capability ↔ external system** — Git host, cluster, cloud model APIs. Egress
  crosses out of Lume's trust domain.
- **Automated action ↔ human approval** — the gate a high-blast or irreversible action
  must cross.

### In-scope threats (Phase 0/1) and primary mitigations

- **Prompt injection** — untrusted content (a repo file, issue, email, web page) steers
  an agent. *Mitigation:* untrusted content is data, never instructions; capabilities
  receive scoped, typed context; the LLM never decides control flow (`done/failures/
  next_action` are deterministic), so injected "do X" cannot change the next action;
  high-blast actions remain gated regardless of what content "asks".
- **Over-permissioned / compromised agent** — an internal identity (or a stolen
  credential) acts beyond scope. *Mitigation:* least-privilege scoped permissions per
  identity (SPIFFE identity + OPA policy), blast-radius gating, no self-approval,
  short-lived rotating credentials (SPIRE SVIDs).
- **Data exfiltration to cloud** — private code/data leaves to a cloud model/service
  without opt-in. *Mitigation:* must-not #1 — no private data egress without explicit
  operator opt-in; egress is a classified, audited, gated action; local-first default.
- **Operator error** — the human approves something destructive or fat-fingers a
  high-blast action. *Mitigation:* approval prompts show blast radius + the
  `applied_effects` that will result + reversibility; `dry_run`; irreversible actions
  extra-gated.

### Designed-for (federation is RESERVED, but the threat is designed against now)

- **Capability supply-chain** — a federated/shared capability is malicious or
  backdoored. *Mitigation:* capabilities must be **signed with verifiable provenance**
  (Sigstore/cosign + SLSA-style provenance); an unverified or newly-pulled capability
  runs at **low trust** until reviewed; all capability actions are still bounded by
  identity + OPA policy + blast-radius (a capability cannot exceed its grant no matter
  what it contains).

### Out of scope for now (acknowledged)

- **Multi-tenant isolation** — Phase 2+ (no second tenant yet); the identity model
  below is designed so tenant identity slots in without rework.

### Adversary goals (what we assume they want)

Exfiltrate private code/data; execute an unauthorised high-blast action (delete, spend,
deploy, external comms); escalate an agent's privilege; tamper with the audit trail to
hide any of the above.

---

## 2. Identity model

### Base levels (static, never mutated)

| Identity | Base trust | Can approve? | Scope |
|---|---|---|---|
| `human` | high | yes (incl. issue grants) | full, subject to audit |
| `claude-code` | elevated | no (cannot self-approve) | broad, but gated on high-blast |
| `lume-agent-*` | standard | no | least-privilege, scoped per SPIFFE identity |
| `lume-agent-local` | low | no | suggest-only; cannot act on high-blast |
| `capability` (each) | derived | no | scoped to its declared MCP tools + artifact class |

Every agent and capability has a **workload identity** (SPIFFE ID via SPIRE), with
short-lived, automatically-rotated credentials (SVIDs) — no long-lived secrets in
agents.

### Earned autonomy = grant overlay (static base + grants)

Earned autonomy (requirements §3) is expressed as **grants**, never by mutating a base
level — so "what can this identity do right now?" stays enumerable as *base + active
grants*:

- A **grant** pre-authorises a **specific action-class** for a **specific identity**
  (e.g. "`lume-agent-coding` may merge Dependabot PRs without human approval").
- Grants are **scoped, revocable, and audited**, and may be bounded (by time, count, or
  blast-radius ceiling).
- **Issuing a grant is itself a high-blast action** — `human` only. An agent therefore
  never self-approves; the operator pre-approved the action-class.
- The grant-issuing *mechanism* (what evidence earns a grant) is deferred (requirements
  §3 open question); this doc fixes only the model.

> This makes earned autonomy concrete and reversible, and supersedes CLAUDE.md's
> absolute "High always requires human approval — no exceptions" (now the default, with
> grants as the exception path). Reconciliation tracked in WORK-0015.

---

## 3. Blast-radius controls

- **Tiers:** `none | low | medium | high` (per CLAUDE.md). Every MCP tool **declares**
  its blast radius (and an `irreversible` flag); the orchestrator classifies each action
  at the blast-radius step using that declaration plus the action's `applied_effects`.
- **Enforcement** happens deterministically at the permission-check step via a **policy
  engine (OPA)**: `(identity base + active grants) × action blast-radius` → allow /
  require-approval / deny. No inference.
- **Approval authority:** `high` (and irreversible) → human approval by default; a
  matching active grant may pre-authorise a specific class. `medium` → standard policy;
  `low`/`none` → proceed under scope. `lume-agent-local` can never act on `high`.
- **Per-tool classification** (routed from WORK-0003): each capability tool's blast
  radius and required trust are declared in its tool contract; the delete tools
  (`delete_workload_manifest`, `delete_provisioned_artifact`) are `high`.

---

## 4. Audit requirements

- **What is logged:** every step of the pipeline for every MCP call — resolved
  identity, permission decision (+ which grant, if any), blast-radius classification,
  validation result, execution outcome, and `applied_effects`. The audit log is the
  source of truth for "what happened."
- **Where:** an **append-only** store, separate from mutable workflow state.
- **Tamper-evidence:** records are **chained and signed** (a hash-chain + signature,
  e.g. Sigstore/cosign) so any deletion or edit is detectable. Tampering with the audit
  trail is an explicit adversary goal (§1), so the log's integrity is a hard
  requirement.
- **Emission/observability:** audit events are emitted via **OpenTelemetry** so the Obs
  capability can consume them — but the signed append-only log, not the telemetry
  pipeline, is the authoritative record.
- **Retention:** security-relevant audit records are retained **permanently** by
  default (configurable per deployment); never silently truncated.

---

## 5. Build vs adopt

Per the guiding stance — adopt primitives, build the glue and AI-native defences:

| Security capability | Decision | Basis |
|---|---|---|
| Workload/agent identity | **ADOPT** | SPIFFE/SPIRE — short-lived rotating SVIDs |
| Policy / blast-radius enforcement | **ADOPT (wrap)** | OPA — deterministic policy engine |
| Audit emission / observability | **ADOPT** | OpenTelemetry — standard emission |
| Audit tamper-evidence (signing) | **ADOPT** | Sigstore/cosign or signed hash-chain |
| Capability signing + provenance | **ADOPT** | Sigstore cosign + SLSA-style provenance |
| Secrets management | **EVALUATE** | needs a candidate (e.g. SOPS / external-secrets) — spike |
| Prompt-injection defence | **BUILD** | Lume-specific AI-native defence (see §1 mitigation) |
| The 6-step pipeline glue | **BUILD** | orchestrator wiring of the pipeline — glue, not primitives |

Nothing here is a paid runtime dependency (all candidates are Apache-2.0/MIT) — consistent
with the OSS-only-by-default principle.

---

## 6. Known open questions / deferred

- **Security-stack spike (recommended, not yet in the backlog)** — validate SPIRE, OPA,
  and signing on k3s in the devcontainer, and the per-MCP-call latency they add. There
  is no dedicated security spike in Phase 0 today; recommend adding one (raise with the
  high-level plan, WORK-0014).
- **Earned-autonomy grant mechanism** — what evidence earns a grant, and the
  thresholds; deferred (requirements §3).
- **Secrets management tool** — choose and validate a candidate.
- **Prompt-injection defence efficacy** — the build-now defences need adversarial
  testing (a red-team pass), likely alongside the validation-loop spike (WORK-0011).
- **Multi-tenant isolation** — Phase 2+; the identity model is designed to admit tenant
  identity without rework.
- **CLAUDE.md reconciliation (WORK-0015)** — the "High always requires human approval —
  no exceptions" line vs the grant overlay.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
