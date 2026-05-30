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

**Latency** (Python MCP SDK 1.27.2, stdio transport, warm, 100 iterations each):

| steps/task | two-layer mean | direct-baseline mean | orchestrator overhead | p95 (two-layer) |
|-----------:|---------------:|---------------------:|----------------------:|----------------:|
| 1 | 7.8 ms | 3.3 ms | ~4.5 ms | 10.6 ms |
| 3 | 12.9 ms | 10.0 ms | ~2.9 ms | 19.5 ms |
| 10 | 35.6 ms | 32.5 ms | ~3.1 ms | 52.4 ms |

The second MCP layer adds a **constant ~3–4 ms** (one extra stdio round-trip),
**independent of step count** — it does not scale with task size. Each agent MCP call is
~3.3 ms over stdio. All figures are single-digit-to-low-tens of ms; **negligible against
LLM inference** (hundreds of ms to seconds), which dominates any real task.

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
  MCPs is cheap (~3–4 ms/hop) and the cost is constant, not per-step — it will be lost in
  the noise of inference. No reason to flatten the two layers for performance.
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
