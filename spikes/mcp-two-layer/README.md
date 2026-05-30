# Spike: MCP two-layer pattern (WORK-0007)

Disposable Phase-0 proof of concept. Proves the two-layer MCP architecture and measures
its latency. Verdict + rationale: `.work/decisions/ADR-001-mcp-two-layer.md`.

**Scope / not production.** This is a pure latency spike: it deliberately omits the
security pipeline (no identity/blast-radius/audit on tool calls) and input validation
(no clamp on `steps`). **Do not cargo-cult into Phase 1** — Phase-1 tools must enforce the
full WORK-0004 security pipeline and bound caller-supplied counts.

## What it proves

The CLAUDE.md two-layer pattern: an **external client** talks to a **Layer-1 orchestrator
MCP server**, which is itself an **MCP client** of a **Layer-2 agent MCP server**:

```
client (bench.py) --stdio--> orchestrator_server.py --stdio--> agent_server.py
   lume_task(steps)             calls agent_step() x steps        n*n+1
```

- `agent_server.py` — Layer-2 agent MCP server; one typed deterministic tool.
- `orchestrator_server.py` — Layer-1 server AND client of the agent; `lume_task`
  coordinates a multi-step task. Holds **one persistent agent session** in its lifespan
  (steady-state latency, not per-task process spawn).
- `bench.py` — external client; measures the two-layer round-trip and a direct-to-agent
  baseline; the delta isolates the orchestrator-layer overhead.

## Run

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python mcp        # pinned: mcp 1.27.2
.venv/bin/python bench.py suite                      # writes the canonical multi-config run
.venv/bin/python bench.py 200 3                      # or a single config: iterations, steps
```

`results.json` holds the canonical suite (200 iterations/config, configs 1/3/10). The
`.venv` is gitignored.

## Result (this machine, stdio, warm; p50 from results.json)

| steps | two-layer p50 | baseline p50 | orchestrator overhead (p50) | per agent call |
|------:|--------------:|-------------:|----------------------------:|---------------:|
| 1 | 5.51 ms | 2.92 ms | 2.59 ms | 2.92 ms |
| 3 | 12.22 ms | 9.32 ms | 2.89 ms | 3.11 ms |
| 10 | 31.27 ms | 31.21 ms | 0.05 ms | 3.12 ms |

The orchestrator layer adds **one extra MCP round-trip per task** — ~2–3 ms (p50), at the
noise floor by steps=10. Overhead is a noisy difference of two stdio measurements; the
robust finding is single-digit ms, constant per-task, negligible vs LLM inference.
