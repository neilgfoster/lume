# Lume — Security and Auth Requirements

**Status**: in review — approval is recorded by merge of the delivering PR (see Sign-off)
**Author**: Neil Foster (interview), synthesised by Claude Code
**Date**: 2026-05-30
**Work item**: WORK-0004

---

Security requirements for Lume: threat model, identity model, blast-radius controls,
audit, and a build-vs-adopt decision per capability. Builds on the approved
[requirements](requirements.md), [orchestrator design](orchestrator-design.md), and
[agent boundaries](agent-boundaries.md). It is requirements-level (what must be true),
not implementation. Adoption candidates are **recommendations pending a security-stack
spike** (§6) — Phase 0 evaluates, it does not install.

## Guiding stance

- **Adopt the primitives, build only the glue and the AI-native defences.** Identity,
  policy, signing, telemetry are solved — adopt strong OSS. Build only the Lume-specific
  pipeline glue and the defences unique to an agentic system (prompt-injection handling,
  capability provenance, semantic output validation). The "don't build what others do
  much better" must-not, applied to security.
- **The 6-step pipeline is the proposed spine** (latency to be validated by the spike):
  `identity (verified) → permission → blast-radius → validation → execution → audit`.
- **Deterministic security.** Identity, permission, blast-radius, and audit are
  deterministic; the LLM never decides any of them (Principle 1). Inference (PLAN/REFINE)
  *proposes* actions; the deterministic gates *contain* them.

---

## 1. Threat model

### Trust boundaries

- **External client ↔ orchestrator** — the single MCP entry point; the only externally
  reachable surface.
- **Orchestrator ↔ capability** — internal MCP; **mutually authenticated** (see §2).
  Capabilities are never externally reachable.
- **Capability ↔ external system** — Git host, cluster, cloud model APIs; egress leaves
  Lume's trust domain.
- **Automated action ↔ human approval** — the gate a high-blast/irreversible action
  crosses.

### In-scope threats (Phase 0/1) and primary mitigations

- **Prompt injection** — untrusted content (repo file, issue, email, web page) steers an
  agent. The **PLAN step is inference and is the primary injection surface**: injected
  content can steer decomposition to add an individually-valid-but-malicious step.
  *Mitigations:* (a) untrusted content is **tagged data, never instructions** — it enters
  an LLM only via clearly-delimited, provenance-tagged data fields, never concatenated
  into the instruction/planning region, and is resolved by a capability during ACT, not
  fed verbatim to the planner; (b) a steered PLAN still **cannot escape the gates** —
  identity + OPA scope + blast-radius + human approval bound every resulting action
  regardless of what content "asked"; (c) **semantic output validation** (below) catches
  malicious-but-schema-valid outputs. The protection is the gates and the data/instruction
  separation — *not* the determinism of the VALIDATE `next_action` enum.
- **Over-permissioned / compromised agent** — an internal identity or stolen credential
  acts beyond scope. *Mitigation:* least-privilege scoped permissions per identity
  (SPIFFE + OPA), blast-radius gating, no self-approval, short-lived rotating SVIDs with
  **per-call verification** (§2).
- **Data exfiltration to cloud** — private code/data reaches a cloud model/service
  without opt-in. *Mitigation:* must-not #1; every context payload is **classified at
  ingestion** with a confidentiality label; cloud escalation checks all in-scope payloads
  are at/below the operator's cloud-egress ceiling and **strips or blocks (never silently
  sends)** above it; egress is classified, audited, gated; local-first default.
- **Operator error / approval spoofing** — the human approves something destructive, or
  is socially-engineered by a benign-washed `applied_effects` self-report. *Mitigation:*
  approval prompts for medium/high show the **actual change** — the rendered diff from the
  write-ahead record (orchestrator design §3), not only the capability's self-reported
  `applied_effects` — plus blast radius and reversibility; `dry_run`; irreversible
  actions extra-gated.
- **Capability semantic maliciousness** — a capability's LLM emits schema-valid,
  policy-compliant, but semantically harmful output (backdoored code, a `NodePort` on a
  sensitive service, credential-shaped strings). *Mitigation:* **semantic output
  validation** as a distinct deterministic layer — known-bad-pattern rules over
  high-consequence outputs (manifest diffs, code patches), separate from schema validation.
- **Denial-of-wallet** — runaway cloud escalation exhausts budget. *Mitigation:*
  deterministic **per-identity and per-deployment cloud-escalation rate/spend limits** and
  a circuit breaker that halts and surfaces a blocked state at the ceiling (a
  resource-consumption blast radius, §3).

### Designed-for (federation is RESERVED, but defended against now)

- **Capability supply-chain** — a federated/shared capability is malicious. *Mitigation:*
  capabilities must be **signed with verifiable provenance** (Sigstore/cosign +
  SLSA-style); unverified/newly-pulled capabilities run at **low trust until reviewed**
  (the review-to-trusted transition is itself an audited grant, §2); all actions are
  bounded by identity + OPA + blast-radius regardless of capability contents; signing
  covers the artifact, **semantic output validation covers runtime behaviour**.

### Out of scope for now (acknowledged)

- **Multi-tenant isolation** — Phase 2+; the identity model admits tenant identity
  without rework.

### Adversary goals

Exfiltrate private code/data; execute an unauthorised high-blast action (delete, spend,
deploy, external comms); escalate an agent's privilege (incl. via composed low-blast
steps); tamper with the audit trail to hide any of the above.

---

## 2. Identity model

### Base levels (static, never mutated)

| Identity | Base trust | Can approve? | Scope |
|---|---|---|---|
| `human` | high | yes (incl. issue grants) | full, subject to audit |
| `claude-code` | elevated | no (cannot self-approve) | broad; gated on high-blast |
| `lume-agent-*` | standard | no | least-privilege, scoped per SPIFFE identity |
| `lume-agent-local` | low | no | suggest-only; cannot act on high-blast |
| `capability` (each) | standard until reviewed; low if unverified | no | scoped to its declared tools + artifact class |

Every agent and capability has a **workload identity** (SPIFFE ID via SPIRE) with
short-lived, automatically-rotated SVIDs (max validity stated by the spike, target ≤5
min) — no long-lived secrets in agents.

**Identity must be verified, not just issued.** All internal MCP transport uses **mutual
TLS with per-call SVID verification** on both sides (orchestrator verifies the
capability's SVID; capability verifies the orchestrator's). The internal MCP socket is
unreachable without a valid SVID. Each capability response carries a **nonce/sequence
bound to the orchestrator's request** to prevent replay within the SVID window. A SPIRE
adoption that issues but does not verify SVIDs is not a control.

### Earned autonomy = grant overlay (static base + grants)

Earned autonomy (requirements §3) is expressed as **grants**, never by mutating a base
level — so "what can this identity do right now?" stays enumerable as *base + active
grants*. This includes the capability low→reviewed transition: raising a reviewed
capability's effective trust is realised as an audited grant, not a base-level mutation.

- A **grant** pre-authorises a typed **action-class** for a specific identity. An
  action-class is a **predicate**: `tool name + argument-constraint expression +
  optional blast-radius ceiling` (e.g. `merge_pr where author == 'dependabot[bot]'`). An
  action is pre-authorised only if it **matches the predicate AND falls within the
  grant's bound** — a tool-name-only match is not sufficient.
- Grants are **scoped, revocable, audited**, and may be bounded (time, count,
  blast-radius ceiling).
- **Issuing a grant is itself a high-blast action — `human` only.** An agent never
  self-approves; the operator pre-approved the action-class.
- The grant-*earning* mechanism (what evidence merits a grant) is deferred (requirements
  §3). This doc fixes the grant *model and matching semantics*.

> The grant overlay supersedes CLAUDE.md's absolute "High always requires human approval
> — no exceptions" (now the default, grants the exception path). Until WORK-0015 edits
> CLAUDE.md, that line governs and no high-blast grant is issued.

---

## 3. Blast-radius controls

- **Tiers and rubric.** `none | low | medium | high`, assigned by a **testable rubric**
  (not author judgment alone): **high** = irreversible OR cloud spend OR external comms
  OR cross-tenant effect; **medium** = reversible in-cluster desired-state change; **low**
  = side-effect-free write to Lume-internal state; **none** = pure read. Every tool
  declares its tier + `irreversible` flag in its contract; the declared tier is reviewed
  against the rubric (self-declaration alone is not trusted).
- **Per-tool coverage** (from WORK-0003): the delete tools (`delete_workload_manifest`,
  `delete_provisioned_artifact`, and Obs's delete path in `write_obs_artifact`) are
  `high`; `write_crossplane_claim` (cloud spend) is `high`; tools with external side
  effects (triggering CI, posting work-item/external comms) are at least `medium`.
- **Enforcement** is deterministic at the permission step via **OPA**:
  `deny if identity.base_trust < tool.required_trust`, then
  `(identity base + active grants) × blast-radius → allow | require-approval | deny`.
  Required-trust is a precondition composed *before* the blast-radius check — not a
  redundant field.
- **Cumulative / workflow-level blast.** Beyond per-step: a workflow's cumulative
  `applied_effects[]` are scored against spend / data-movement / irreversibility budgets,
  so a sequence of individually-low-blast steps that sums to a high effect is gated. This
  is distinct from per-tool classification.
- **Approval authority.** `high`/irreversible → human by default (a matching active grant
  may pre-authorise a class). `medium` → policy; `low`/`none` → proceed under scope.
  `lume-agent-local` can never act on `high`. **Cloud-escalation limits** (rate/spend per
  identity and per deployment, with a circuit breaker) are enforced here as a
  resource-consumption blast radius.

---

## 4. Audit requirements

- **Owner.** The **orchestrator** is the sole writer of the audit log (orchestrator
  design §1); no agent or capability may write or mutate it.
- **What is logged:** every pipeline step for every MCP call — resolved+verified
  identity, permission decision (+ which grant, if any), blast-radius classification,
  validation result, execution outcome, and `applied_effects`. The log is the source of
  truth for "what happened."
- **Where:** an **append-only** store, separate from mutable workflow state.
- **Tamper-evidence:** records are **chained and signed** so any deletion/edit is
  detectable. **The signing key lives in a separate trust domain from the orchestrator
  runtime** (e.g. a transparency log such as Sigstore/Rekor, or a hardware-backed/separate
  identity), so a compromised orchestrator cannot re-sign a tampered chain. Key rotation
  is itself an audited, human-gated action.
- **Access control.** Only `human` and `claude-code` may read raw audit records (via
  `lume_query` scope=audit); `lume-agent-*` receive only scoped, redacted summaries —
  raw audit (past high-blast actions, pending grants, approval patterns) is not exposed
  to agents.
- **Emission/observability:** events emitted via **OpenTelemetry** for the Obs capability
  to consume — but the signed append-only log, not the telemetry pipeline, is
  authoritative.
- **Retention:** security-relevant records retained **permanently** by default
  (configurable); never silently truncated.

---

## 5. Build vs adopt

Adopt primitives; build the glue and AI-native defences. All ADOPT verdicts are
**recommendations pending the security-stack spike** (§6) — Phase 0 evaluates.

| Security capability | Decision | Basis |
|---|---|---|
| Workload identity (+ per-call verify) | RECOMMEND ADOPT | SPIFFE/SPIRE, mutual-TLS SVIDs |
| Policy / blast-radius enforcement | RECOMMEND ADOPT (wrap) | OPA — deterministic policy |
| Audit emission / observability | RECOMMEND ADOPT | OpenTelemetry |
| Audit tamper-evidence (signing) | RECOMMEND ADOPT | Sigstore/Rekor or signed hash-chain |
| Capability signing + provenance | RECOMMEND ADOPT | Sigstore cosign + SLSA-style |
| Secrets management | EVALUATE | candidate + criteria in §6 |
| Prompt-injection defence | BUILD | content-as-tagged-data + gates (see §1) |
| Semantic output validation | BUILD | known-bad-pattern rules over high-consequence outputs |
| Context confidentiality classification | BUILD | label-at-ingestion + cloud-egress ceiling |
| The 6-step pipeline glue | BUILD | orchestrator wiring — glue, not primitives |

Candidate licences are Apache-2.0/MIT (to be confirmed in the spike) — no paid runtime
dependency, consistent with OSS-only-by-default.

---

## 6. Known open questions / deferred

**Blocks Phase 1 entry:**

- **Security-stack spike (not yet in the backlog)** — validate SPIRE, OPA, and signing on
  k3s in the devcontainer; measure per-MCP-call latency of the 6-step pipeline; confirm
  candidate licences. Recommend adding a dedicated spike (raise with the plan, WORK-0014).
- **Earned-autonomy grant-earning mechanism** — soft-dependent on WORK-0015 (the CLAUDE.md
  "no exceptions" reconciliation must land first).

**Does not block Phase 1 entry:**

- **Secrets management** — choose a candidate against criteria: encrypted-at-rest;
  never appears in any audit/telemetry record; integrates with SPIRE so agents *fetch*
  rather than store; secrets never mounted where a capability's MCP tools (e.g.
  `read_files`) or its LLM context can read them.
- **Prompt-injection & semantic-validation efficacy** — adversarial red-team pass,
  alongside the validation-loop spike (WORK-0011).
- **Multi-tenant isolation** — Phase 2+.

**Tracking:** CLAUDE.md reconciliation of the "no exceptions" line is WORK-0015.

---

## Sign-off

Approval is **recorded by the merge of this document's delivering PR** — the operator's
review-and-merge is the approval gate (per the `/iterate` flow). There is no separate
in-file approval step; an unmerged PR means not-yet-approved.
