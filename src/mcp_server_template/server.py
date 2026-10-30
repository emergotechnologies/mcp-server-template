"""Builds the MCP server. Used by both transports and by the tests."""

from mcp.server.mcpserver import MCPServer

from mcp_server_template import __version__, prompts, resources, tools
from mcp_server_template.auth import oauth_components
from mcp_server_template.config import Settings

SERVER_NAME = "mcp-server-template"


def create_server(settings: Settings) -> MCPServer:
    token_verifier, auth_settings = oauth_components(settings)
    mcp = MCPServer(
        SERVER_NAME,
        version=__version__,
        log_level=settings.log_level,
        token_verifier=token_verifier,
        auth=auth_settings,
    )
    tools.register(mcp)
    resources.register(mcp)
    prompts.register(mcp)
    return mcp
