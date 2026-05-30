"""Layer-2 agent MCP server (PoC).

Stands in for a downstream Lume agent: exposes one typed, deterministic MCP tool.
Runs over stdio. Disposable Phase-0 spike code.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lume-agent-poc")


@mcp.tool()
def agent_step(n: int) -> int:
    """A deterministic unit of agent work (stand-in): returns n*n + 1."""
    return n * n + 1


if __name__ == "__main__":
    mcp.run()  # stdio transport
