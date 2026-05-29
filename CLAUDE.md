# Lume — CLAUDE.md

An AI-native internal developer platform (IDP). MCP-first architecture.
Runs on Kubernetes from a single developer laptop to full enterprise scale.
Built using dev containers — the only host requirement is Docker.

**The single most important principle:**
Claude Code is scaffolding. The destination is `lume "do thing"` —
a platform that builds and operates itself, with no knowledge of the
underlying AI, agents, or infrastructure required from the user.

---

## The vision

A developer types `lume "add rate limiting to the API gateway"`. Lume understands
the intent, decomposes it, coordinates the right specialist agents, writes code,
runs tests, provisions infra via GitOps, tracks the work item, and reports back
with a PR link. The developer never specifies which agents ran, which models were
used, or how the infra was provisioned. That complexity is Lume's problem
permanently. Over time, Lume handles more of its own development — building new
features, fixing its own bugs, improving its own agents — until Claude Code is an
optional power tool rather than a daily requirement.

---

## Non-negotiable principles

These govern every decision. Never violate them.

1. **Deterministic over inference** — if a function can do it, an LLM must not
2. **Validation loops** — every agent output validated before proceeding
3. **Token efficiency** — compress context, escalate models only when local fails
4. **Local first** — local models handle grunt work, cloud only when needed
5. **MCP is the interface** — every agent action goes through typed MCP tools
6. **Client agnostic** — MCP surface works for Claude Code, CLI, web, Lume itself
7. **GitOps everything** — Lume writes config to Git, operators reconcile reality
8. **One work item at a time** — finish and validate before starting the next
9. **Phase discipline** — nothing built outside the current phase scope
10. **OSS only** — no paid runtime dependencies

---

## Architecture

### External interface

All external tools talk to Lume through a single entry point:
the Lume Orchestrator MCP server. No external tool ever talks to
an agent directly. The orchestrator is not a router — it is an
agent that reasons, decomposes tasks, coordinates other agents,
tracks multi-agent workflow state, and returns coherent results.

```
External clients (any MCP client):
  Claude Code  ·  lume CLI  ·  lume web  ·  Lume itself

         │  one MCP connection
         ▼
  Lume Orchestrator Agent
  reasons · decomposes · coordinates · tracks state

         │  internal only (never MCP-exposed externally)
         ▼
  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  │ Coding   │ Infra    │ Work     │Provision │  Obs     │
  │ Agent    │ Agent    │ Agent    │ Agent    │ Agent    │
  └──────────┴──────────┴──────────┴──────────┴──────────┘
         │
  [Agent MCP tools — deterministic — typed — validated]
         │
  [Validation loop: plan → act → validate → refine → escalate]
```

### The two-layer MCP pattern

Layer 1 (external): Lume Orchestration MCP — what Claude Code talks to.
  Maximum 5 tools. Intent-based. Client-agnostic.
  Provisional tools: lume_task, lume_query, lume_status, lume_approve, lume_context

Layer 2 (internal): Agent MCPs — deterministic typed tools per agent.
  Agents use LLM inference to plan. MCP tools to act. Never mixed.
  External tools never see or call these.

### Agent control loop

```
[PLAN]     inference — LLM breaks task into steps
[ACT]      deterministic — MCP tool executes one step
[VALIDATE] deterministic — validation suite runs, produces structured result
           done: boolean        ← LLM never infers success
           failures: Finding[]  ← LLM never infers what broke
           next_action          ← LLM never infers what to do next
[REFINE]   inference (if FAIL) — targeted prompt on failures only
[ESCALATE] if retries exhausted → larger local model → cloud → human
```

### GitOps separation

```
lume/     ← Lume itself (this repo — AI orchestration system)
config/   ← what Lume manages (GitOps state, tenant config)
```

Lume never provisions infrastructure directly. It writes declarative config to Git.
GitOps operators (Flux or Argo CD) reconcile to reality. Crossplane handles
infrastructure claims.

### Provisioning Agent

Infra Agent: manages existing infrastructure (scale, debug, observe)
Provisioning Agent: creates new things by writing config to Git

Provisioning Agent MCP tools (all write to Git, never apply directly):
  provision_repo, provision_tenant, write_gitops_config,
  write_crossplane_claim, bootstrap_lume_project

---

## The autonomy arc

```
Phase 0-1 (Scaffolded):  Human → Claude Code → Lume MCP
Phase 2-3 (Collaborative): Lume handles routine tasks. Claude for novel problems.
Phase 4 (Capable):       lume CLI/Web is primary interface.
Phase 5 (Self-directing): Lume plans, implements, validates, ships autonomously.
```

---

## Dev environment

Single host requirement: Docker.

```
.devcontainer/
  devcontainer.json, docker-compose.yml, Dockerfile

Local stack (docker compose):
  k3s, Crossplane, Flux/Argo, Gitea, Ollama, Registry
```

Volume strategy:
- Source code: bind mount (survives rebuild)
- Ollama models: named volume (survives rebuild)
- Gitea data: named volume (survives rebuild)
- k3s state: ephemeral (intentionally disposable)

---

## Security model

Every MCP tool call passes through:
  identity resolution → permission check → blast radius →
  validation → execution → audit log (append-only, signed)

Blast radius: none / low / medium / high
High always requires human approval — no exceptions.

Identity levels:
  human: trust:high, can approve
  claude-code: trust:elevated, cannot self-approve
  lume-agent-*: trust:standard, scoped permissions
  lume-agent-local: trust:low, suggest only

---

## Model routing

```
Router / classification     → llama3.2:3b      (local, instant)
Code generation / review    → qwen2.5-coder:7b  (local)
Complex coding tasks        → qwen2.5-coder:14b (local, slower)
Hard reasoning              → claude-sonnet     (cloud, targeted)
Novel problems / escalation → claude-opus       (cloud, last resort)
File summarisation          → local model       (never burn cloud tokens)
```

Escalation:
- Local fails after 2 attempts → escalate to larger local model
- Local fails after 4 attempts → escalate to cloud (one targeted call)
- Cloud fails or unavailable → surface as blocked work item

---

## Adversarial review

Panel selected by task type:
```
Coding:       Security Auditor, Edge Case Hunter, Scope Auditor
Infra:        Chaos Engineer, Security Auditor, Operator
Architecture: Historian, Devil's Advocate, Simplicity Enforcer
Requirements: Ambiguity Hunter, Contradiction Finder, Scope Auditor
Phase review: Evidence Checker, Assumption Challenger, Scope Auditor, Historian
Self review:  Existential Challenger, Drift Detector, Historian, Devil's Advocate
```

Verdict: PASS / CONDITIONAL / FAIL
FAIL blocks proceeding. FAIL x2 surfaces to human.
Phase transition requires phase review panel — cannot be skipped.

---

## Reference projects

- **kagent** (kagent.dev) — agent runtime on k8s, CRD-based
- **Cloudflare iMARS** — production two-layer MCP architecture at scale
- **OpenChoreo** — IDP plane separation pattern (CNCF sandbox, Jan 2026)
- **oh-my-claudecode** — session-level agent orchestration
- **hedl** — project discipline layer (phase gates, adversarial review, am_i_done)

---

## Phase 0 — Discovery & Requirements (ACTIVE)

**Goal:** Understand before building. No production code. Everything disposable.
Validate assumptions. Produce an approved plan. Green light before Phase 1.

**Constraints:**
- No production code — spikes and proofs of concept only
- No Lume-specific implementation — evaluate tools and patterns only
- Everything disposable — nothing from Phase 0 ships in Phase 1
- Write conclusions, not just notes — every spike produces a decision

**Definition of Done:**

Requirements (Neil must approve each):
- [ ] Core requirements doc — what Lume must do, must not do, success metrics
- [ ] Orchestrator design — responsibilities, MCP surface, state model, failure model
- [ ] Agent boundary analysis — each agent: responsibilities, MCP tools, validation suite
- [ ] Security and auth requirements — threat model, identity model, blast radius controls
- [ ] Data and state architecture — what state, where, how it flows, context store design
- [ ] CLI and self-building requirements — command surface, approval gates, rollback

Architecture spikes (each produces a GO/NO-GO verdict + ADR):
- [ ] MCP SDK + two-layer pattern — prove orchestrator MCP calling agent MCP
- [ ] kagent evaluation — can it be Lume's agent runtime?
- [ ] GitOps operator + Crossplane on k3s — Flux vs Argo decision
- [ ] Local model evaluation — actual task performance measurements
- [ ] Validation loop proof of concept — standalone, not in Lume

Design (Neil must approve):
- [ ] Provisioning agent boundary — tools, bootstrap flow, config structure
- [ ] Project template — what every Lume-provisioned project gets
- [ ] High-level plan — phases 1-3 with draft DoD, known unknowns, risks

Phase 0 complete when all items above verified and Neil gives green light.
