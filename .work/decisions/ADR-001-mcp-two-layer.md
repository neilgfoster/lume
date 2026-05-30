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

- **Python MCP SDK** (`mcp` 1.27.2, official; `FastMCP` server API) — used here. Mature,
  ergonomic (decorator tools, typed I/O, structured results), supports **stdio** and
  **streamable-HTTP** transports. Server-as-client nesting (the orchestrator) is clean via
  the server lifespan. Best fit for Lume's internal servers (orchestrator + agents are
  Python-leaning: local models, validation loop).
- **TypeScript MCP SDK** (`@modelcontextprotocol/sdk`, official) — equally first-class;
  the better choice for the `lume web` client and Node-based external clients. Not needed
  for internal Layer-1/Layer-2 servers.
- **Transport:** **stdio** for local/co-located processes (used in the PoC; ideal for the
  single-desktop profile). **streamable-HTTP** for networked/enterprise deployment —
  RESERVED, to be validated when scale demands it.

## Decision

**GO on the two-layer MCP pattern.** Adopt the **official Python MCP SDK** for the Layer-1
orchestrator and Layer-2 agent servers; reserve the TypeScript SDK for web/Node clients.
Default to **stdio** transport for the local profile; treat **streamable-HTTP** as the
RESERVED networked-scale transport. The orchestrator must hold **persistent** sessions to
its agents (PoC pattern), not spawn a process per task.

## Consequences

- The architecture's central premise is validated: layering the orchestrator over agent
  MCPs is cheap (~2–3 ms/hop p50, often at the measurement noise floor) and the cost is
  constant, not per-step — it will be lost in the noise of inference. No reason to flatten
  the two layers for performance.
- **Server-as-client nesting works**: the orchestrator being both an MCP server and an MCP
  client (via lifespan-managed agent sessions) is a clean, supported pattern — this is how
  Layer 1 coordinates Layer 2.
- **Confirms a WORK-0005 assumption**: persistent agent sessions (not per-task spawn) are
  required for steady-state latency; per-task process spawn would dominate.
- **Open / deferred:** (a) the **streamable-HTTP transport** at networked scale is
  unmeasured — validate in a later spike before enterprise deployment; (b) latency was
  measured with a trivial agent tool — real agents add their own work, but that is agent
  cost, not transport cost; (c) the PoC used a single agent — fan-out to 5+ agents
  (CLAUDE.md) was not stress-tested, though the constant per-hop cost predicts it scales
  linearly in hops, not super-linearly.
- Supersedes nothing. Informs WORK-0008 (kagent — does its runtime expose agents over
  MCP the same way?) and WORK-0014 (the high-level plan).
