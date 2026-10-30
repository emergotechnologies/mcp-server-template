"""Prompts: reusable message templates. Add new prompts inside `register`."""

from mcp.server.mcpserver import MCPServer


def register(mcp: MCPServer) -> None:
    @mcp.prompt()
    def code_review(code: str) -> str:
        """Ask for a review of a piece of code."""
        return f"Please review the following code and point out bugs and possible improvements:\n\n{code}"
