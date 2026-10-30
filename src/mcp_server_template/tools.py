"""Tools: functions the model can call. Add new tools inside `register`."""

from mcp.server.mcpserver import MCPServer


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    def add(a: float, b: float) -> float:
        """Add two numbers and return the sum."""
        return a + b
