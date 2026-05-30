# ADR-001-mcp-two-layer

## Status

Accepted — **GO**. (Phase 0 spike WORK-0007; PoC in `spikes/mcp-two-layer/`.)

## Context

CLAUDE.md's external interface is a **two-layer MCP** architecture: external clients talk
only to a **Layer-1 orchestrator MCP server**, which coordinates **Layer-2 agent MCP
servers** (never exposed externally). Before committing Phase 1 to this, the spike had to
prove it works in practice, measure the latency the second layer adds, and evaluate the
SDK options.

**What was built** (`spikes/mcp-two-layer/`, disposable): a Layer-2 `agent_server.py`
(one typed deterministic tool), a Layer-1 `orchestrator_server.py` that is simultaneously
an MCP *server* to the external client and an MCP *client* of the agent (its `lume_task`
tool coordinates a multi-step task by calling the agent N times), and a `bench.py`
external client. The full path **client → orchestrator MCP → agent MCP → result** runs.

**Latency** (Python MCP SDK 1.27.2, stdio, warm, 200 iterations/config; figures are
**p50**, taken verbatim from the committed `results.json`):

| steps/task | two-layer p50 | direct-baseline p50 | orchestrator overhead (p50) | per agent call (p50) |
|-----------:|--------------:|--------------------:|----------------------------:|---------------------:|
| 1 | 5.51 ms | 2.92 ms | 2.59 ms | 2.92 ms |
| 3 | 12.22 ms | 9.32 ms | 2.89 ms | 3.11 ms |
| 10 | 31.27 ms | 31.21 ms | 0.05 ms | 3.12 ms |

The orchestrator layer adds **one extra MCP round-trip per task** — measured at **~2–3 ms
(p50)**, and at steps=10 the difference is at the **noise floor** (~0 ms). Overhead is a
difference of two noisy stdio measurements, so the absolute ms vary run to run (an earlier
single 100-iter run showed baseline jitter inflating it to ~9 ms); the **robust** finding
is the order of magnitude — **single-digit ms, a constant per-task hop (not per-step)** —
and that it is **negligible against LLM inference** (hundreds of ms to seconds), which
dominates any real task. Each agent MCP call is ~3 ms over stdio.

**SDK options evaluated:**

- **Python MCP SDK** (`mcp` 1.27.2, official, **MIT — OSS, satisfies principle 10**;
  `FastMCP` server API) — **exercised here**. Mature, ergonomic (decorator tools, typed
  I/O, structured results), supports **stdio** and **streamable-HTTP** transports.
  Server-as-client nesting (the orchestrator) is clean via the server lifespan. Good fit
  for Lume's internal servers (orchestrator + agents are Python-leaning: local models,
  validation loop).
- **TypeScript MCP SDK** (`@modelcontextprotocol/sdk`, official) — **assessed on
  documentation only; not exercised in this spike.** It is the natural choice for the
  `lume web` client and Node-based external clients; the server-as-client nesting pattern
  was *not* verified in TS. This is a provisional lean, to be validated when `lume web` is
  built — not a measured result.
- **Transport:** **stdio** for local/co-located processes (used in the PoC; ideal for the
  single-desktop profile). **streamable-HTTP** for networked/enterprise deployment —
  RESERVED, to be validated when scale demands it.

## Decision

**GO on the two-layer MCP pattern** — the layering (orchestrator-MCP coordinating
agent-MCP) is proven and architecturally sound. Adopt the **official Python MCP SDK** (MIT)
for the Layer-1 orchestrator and Layer-2 agent servers; the orchestrator must hold
**persistent** sessions to its agents (PoC pattern), not spawn a process per task.

Two bounds on this GO, kept explicit:

- **The *performance* GO is bounded to the local, co-located stdio profile.** The
  ~2–3 ms-per-hop figure is a stdio, single-machine result. CLAUDE.md targets Kubernetes
  scale, where agents may be **networked pods, not stdio child processes** — that hop is
  unmeasured and could be materially larger. **WORK-0008 (kagent) must resolve the agent
  transport**; the enterprise-scale performance claim is gated on it. The *pattern* GO
  stands regardless; only the latency number carries the local-only asterisk.
- **The Python-for-internal-servers choice is proven; the TS-for-web choice is
  provisional** (doc-review only — see Context). `lume web` validates the TS SDK later.
- Transport: **stdio** for the local profile (used here); **streamable-HTTP** RESERVED for
  networked scale (unmeasured, gated on WORK-0008).

## Consequences

- The architecture's central premise is validated: layering the orchestrator over agent
  MCPs is cheap (~2–3 ms/hop p50, often at the measurement noise floor) and the cost is
  constant, not per-step — it will be lost in the noise of inference. No reason to flatten
  the two layers for performance.
- **Server-as-client nesting works**: the orchestrator being both an MCP server and an MCP
  client (via lifespan-managed agent sessions) is a clean, supported pattern — this is how
  Layer 1 coordinates Layer 2.
- **Confirms an orchestrator-design (WORK-0002 §3) assumption**: persistent agent sessions
  (not per-task spawn) are required for steady-state latency; per-task process spawn would
  dominate.
- **The PoC deliberately omits the security pipeline** (no identity/blast-radius/audit on
  the tool calls) and input validation (no clamp on `steps`) — it is a pure latency spike.
  **This code must not be cargo-culted into Phase 1**: Phase-1 tools must enforce the full
  WORK-0004 pipeline and bound caller-supplied loop counts.
- **Open / deferred:** (a) **networked transport** (streamable-HTTP / agents-as-pods) is
  unmeasured — gated on WORK-0008 before any enterprise-scale latency claim; (b) latency
  used a trivial agent tool (isolates transport cost — intentional), but **large
  structured payloads double-marshalled across two layers are unmeasured**; (c) the PoC
  used a **single agent, called sequentially** — fan-out to 5+ agents (CLAUDE.md) with
  concurrency/back-pressure was not tested, so "scales linearly in hops" is a
  **hypothesis**, not a measurement (retest in WORK-0008); (d) TS SDK unexercised (above).
- Supersedes nothing. Informs WORK-0008 (kagent — agent transport + multi-agent fan-out)
  and WORK-0014 (the high-level plan).
