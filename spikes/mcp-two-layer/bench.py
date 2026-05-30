"""Bench harness for the two-layer MCP PoC.

Measures two paths over stdio, each doing the same amount of agent work (`steps`
agent calls per task):

  two_layer: external client -> orchestrator MCP -> agent MCP (x steps) -> result
  baseline:  external client -> agent MCP (x steps) directly

The delta isolates the cost the orchestrator layer adds. Prints JSON stats.
Disposable Phase-0 spike code.
"""

import asyncio
import json
import os
import statistics
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_HERE = os.path.dirname(os.path.abspath(__file__))
_PY = sys.executable
_ORCH = os.path.join(_HERE, "orchestrator_server.py")
_AGENT = os.path.join(_HERE, "agent_server.py")


def _stats(label, lat_ms, **extra):
    lat_ms = sorted(lat_ms)
    n = len(lat_ms)
    return {
        "path": label,
        **extra,
        "iterations": n,
        "mean_ms": round(statistics.mean(lat_ms), 3),
        "p50_ms": round(lat_ms[n // 2], 3),
        "p95_ms": round(lat_ms[min(int(n * 0.95), n - 1)], 3),
        "min_ms": round(lat_ms[0], 3),
        "max_ms": round(lat_ms[-1], 3),
    }


async def _measure(server_path, tool, args, iterations, warmup=5):
    params = StdioServerParameters(command=_PY, args=[server_path])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for _ in range(warmup):
                await session.call_tool(tool, args)
            lat = []
            for _ in range(iterations):
                t0 = time.perf_counter()
                await session.call_tool(tool, args)
                lat.append((time.perf_counter() - t0) * 1000.0)
            return lat


async def _baseline(steps, iterations, warmup=5):
    """Client -> agent directly, doing `steps` agent calls per measured task."""
    params = StdioServerParameters(command=_PY, args=[_AGENT])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for _ in range(warmup):
                for i in range(steps):
                    await session.call_tool("agent_step", {"n": i})
            lat = []
            for _ in range(iterations):
                t0 = time.perf_counter()
                for i in range(steps):
                    await session.call_tool("agent_step", {"n": i})
                lat.append((time.perf_counter() - t0) * 1000.0)
            return lat


async def main(iterations=100, steps=3):
    two_layer = await _measure(_ORCH, "lume_task", {"steps": steps}, iterations)
    baseline = await _baseline(steps, iterations)
    two = _stats("two_layer (client->orch->agent)", two_layer, steps=steps)
    base = _stats("baseline (client->agent direct)", baseline, steps=steps)
    overhead_ms = round(two["mean_ms"] - base["mean_ms"], 3)
    out = {
        "steps_per_task": steps,
        "two_layer": two,
        "baseline": base,
        "orchestrator_layer_overhead_mean_ms": overhead_ms,
        "per_agent_call_mean_ms": round(base["mean_ms"] / steps, 3),
    }
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    st = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    asyncio.run(main(it, st))
