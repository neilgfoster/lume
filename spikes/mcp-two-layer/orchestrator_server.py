"""Layer-1 orchestrator MCP server (PoC).

Proves the two-layer pattern: it is an MCP *server* to the external client AND an
MCP *client* to the Layer-2 agent. A persistent agent session is opened once in the
server lifespan (steady-state latency, not per-task process spawn), and `lume_task`
coordinates a multi-step task by calling the agent tool `steps` times.

Disposable Phase-0 spike code. Runs over stdio.
"""

import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import Context, FastMCP

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT = os.path.join(_HERE, "agent_server.py")
_PY = sys.executable


@dataclass
class OrchState:
    agent: ClientSession


@asynccontextmanager
async def lifespan(_server: FastMCP):
    """Open one persistent client session to the Layer-2 agent for the lifetime."""
    async with AsyncExitStack() as stack:
        params = StdioServerParameters(command=_PY, args=[_AGENT])
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        yield OrchState(agent=session)


mcp = FastMCP("lume-orchestrator-poc", lifespan=lifespan)


def _value(result) -> int:
    """Extract the agent's int return from a CallToolResult (structured or text)."""
    sc = getattr(result, "structuredContent", None)
    if sc and "result" in sc:
        return int(sc["result"])
    return int(result.content[0].text)


@mcp.tool()
async def lume_task(steps: int, ctx: Context) -> dict:
    """Coordinate a multi-step task: call the Layer-2 agent `steps` times, aggregate."""
    state: OrchState = ctx.request_context.lifespan_context
    acc = 0
    for i in range(steps):
        res = await state.agent.call_tool("agent_step", {"n": i})
        acc += _value(res)
    return {"steps": steps, "result": acc}


if __name__ == "__main__":
    mcp.run()  # stdio transport
