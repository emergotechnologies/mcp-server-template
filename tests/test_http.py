import logging
from collections.abc import Iterator

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import SecretStr

from mcp_server_template.config import Settings
from mcp_server_template.http_app import build_http_app

from .conftest import TOKEN, serve

PUBLIC_URL = "https://example.ngrok-free.app"


@pytest.fixture
def no_auth_url() -> Iterator[str]:
    with serve(build_http_app(Settings(transport="http"))) as url:
        yield url


@pytest.fixture
def bearer_url() -> Iterator[str]:
    settings = Settings(transport="http", auth_mode="bearer", auth_token=SecretStr(TOKEN), public_url=PUBLIC_URL)
    with serve(build_http_app(settings)) as url:
        yield url


def mcp_client(url: str, headers: dict[str, str] | None = None) -> Client:
    return Client(streamable_http_client(f"{url}/mcp", http_client=httpx2.AsyncClient(headers=headers)))


def initialize(url: str, headers: dict[str, str] | None = None) -> httpx2.Response:
    """A raw MCP initialize request, as `curl` in the quick-start guide sends it."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
    }
    accept = {"Accept": "application/json, text/event-stream"}
    return httpx2.post(f"{url}/mcp", json=body, headers=accept | (headers or {}))


def test_healthz(no_auth_url: str) -> None:
    response = httpx2.get(f"{no_auth_url}/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_mcp_over_http_without_auth(no_auth_url: str) -> None:
    async with mcp_client(no_auth_url) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
    assert "5" in result.content[0].text  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_bearer_valid_token(bearer_url: str) -> None:
    async with mcp_client(bearer_url, {"Authorization": f"Bearer {TOKEN}"}) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
    assert "5" in result.content[0].text  # type: ignore[union-attr]


@pytest.mark.parametrize("header", [None, "Bearer wrong-token", f"Basic {TOKEN}"])
def test_bearer_rejects_missing_or_wrong_token(bearer_url: str, header: str | None) -> None:
    response = initialize(bearer_url, {"Authorization": header} if header else None)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


def test_bearer_leaves_healthz_open(bearer_url: str) -> None:
    assert httpx2.get(f"{bearer_url}/healthz").status_code == 200


def test_public_host_is_accepted(bearer_url: str) -> None:
    auth = {"Authorization": f"Bearer {TOKEN}", "Host": "example.ngrok-free.app"}
    assert initialize(bearer_url, auth).status_code == 200


def test_unknown_host_is_rejected(bearer_url: str) -> None:
    auth = {"Authorization": f"Bearer {TOKEN}", "Host": "evil.example.com"}
    response = initialize(bearer_url, auth)
    assert 400 <= response.status_code < 500


def test_localhost_host_is_accepted(bearer_url: str) -> None:
    port = bearer_url.rsplit(":", 1)[1]
    auth = {"Authorization": f"Bearer {TOKEN}", "Host": f"localhost:{port}"}
    assert initialize(bearer_url, auth).status_code == 200


def test_tokens_never_logged(bearer_url: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    initialize(bearer_url, {"Authorization": "Bearer wrong-token-value"})
    initialize(bearer_url, {"Authorization": f"Bearer {TOKEN}"})
    assert "wrong-token-value" not in caplog.text
    assert TOKEN not in caplog.text
