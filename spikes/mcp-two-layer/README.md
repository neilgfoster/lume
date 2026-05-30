# Spike: MCP two-layer pattern (WORK-0007)

Disposable Phase-0 proof of concept. Proves the two-layer MCP architecture and measures
its latency. Verdict + rationale: `.work/decisions/ADR-001-mcp-two-layer.md`.

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
.venv/bin/python bench.py 100 3                      # iterations, steps-per-task
```

`results.json` holds a captured run (100 iterations, 3 steps). The `.venv` is gitignored.

## Result (this machine, stdio, warm)

| steps | two-layer mean | baseline mean | orchestrator overhead | per agent call |
|------:|---------------:|--------------:|----------------------:|---------------:|
| 1 | 7.8 ms | 3.3 ms | ~4.5 ms | 3.3 ms |
| 3 | 12.9 ms | 10.0 ms | ~2.9 ms | 3.3 ms |
| 10 | 35.6 ms | 32.5 ms | ~3.1 ms | 3.2 ms |

The orchestrator layer adds a **constant ~3–4 ms** (one extra stdio MCP round-trip),
independent of step count — single-digit ms, negligible against LLM inference.
