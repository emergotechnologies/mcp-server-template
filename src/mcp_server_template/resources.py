"""Resources: read-only data the client can load. Add new resources inside `register`."""

import json

from mcp.server.mcpserver import MCPServer


def register(mcp: MCPServer) -> None:
    @mcp.resource("info://server", mime_type="application/json")
    def server_info() -> str:
        """Name and version of this server."""
        return json.dumps({"name": mcp.name, "version": mcp.version})

    @mcp.resource("greeting://{name}")
    def greeting(name: str) -> str:
        """A personalised greeting."""
        return f"Hello, {name}!"
