import json

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError

from mcp_server_template import __version__
from mcp_server_template.config import Settings
from mcp_server_template.server import SERVER_NAME, create_server

pytestmark = pytest.mark.anyio


def client() -> Client:
    return Client(create_server(Settings()))


async def test_server_identifies_itself() -> None:
    async with client() as c:
        assert c.server_info is not None
        assert (c.server_info.name, c.server_info.version) == (SERVER_NAME, __version__)


async def test_add_is_listed_with_schema() -> None:
    async with client() as c:
        tools = {tool.name: tool for tool in (await c.list_tools()).tools}
    add = tools["add"]
    assert add.description
    assert set(add.input_schema["required"]) == {"a", "b"}
    assert add.input_schema["properties"]["a"]["type"] == "number"


async def test_add_returns_sum() -> None:
    async with client() as c:
        result = await c.call_tool("add", {"a": 2, "b": 3})
    assert not result.is_error
    assert "5" in result.content[0].text  # type: ignore[union-attr]


async def test_add_rejects_invalid_arguments() -> None:
    async with client() as c:
        result = await c.call_tool("add", {"a": "two", "b": 3})
    assert result.is_error


async def test_info_resource() -> None:
    async with client() as c:
        uris = [str(r.uri) for r in (await c.list_resources()).resources]
        content = (await c.read_resource("info://server")).contents[0]
    assert "info://server" in uris
    assert json.loads(content.text) == {"name": SERVER_NAME, "version": __version__}  # type: ignore[union-attr]


async def test_greeting_template() -> None:
    async with client() as c:
        templates = [t.uri_template for t in (await c.list_resource_templates()).resource_templates]
        content = (await c.read_resource("greeting://Ada")).contents[0]
    assert "greeting://{name}" in templates
    assert "Ada" in content.text  # type: ignore[union-attr]


async def test_code_review_prompt() -> None:
    async with client() as c:
        prompts = {p.name: p for p in (await c.list_prompts()).prompts}
        result = await c.get_prompt("code_review", {"code": "print(1)"})
    assert [(a.name, a.required) for a in prompts["code_review"].arguments or []] == [("code", True)]
    message = result.messages[0]
    assert message.role == "user"
    assert "print(1)" in message.content.text  # type: ignore[union-attr]


async def test_code_review_requires_code() -> None:
    async with client() as c:
        with pytest.raises(MCPError):
            await c.get_prompt("code_review", {})
