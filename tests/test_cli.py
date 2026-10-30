import json
import logging
import os
import signal
import subprocess
import sys
import time

import httpx2
import pytest
import uvicorn
from mcp import Client, StdioServerParameters

from mcp_server_template import cli
from mcp_server_template.config import Settings

from .conftest import TOKEN

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
}


@pytest.fixture
def chosen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which transport `main` dispatches to instead of starting a server."""
    calls: list[str] = []
    monkeypatch.setattr(cli, "run_stdio", lambda settings: calls.append("stdio"))
    monkeypatch.setattr(cli, "run_http", lambda settings: calls.append("http"))
    return calls


def test_default_transport_is_stdio(chosen: list[str]) -> None:
    cli.main([])
    assert chosen == ["stdio"]


def test_env_selects_http(chosen: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    cli.main([])
    assert chosen == ["http"]


def test_flag_overrides_env(chosen: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    cli.main(["--transport", "stdio"])
    assert chosen == ["stdio"]


def test_invalid_transport_exits(chosen: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--transport", "pigeon"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "MCP_TRANSPORT" in err
    assert "'stdio'" in err
    assert "'http'" in err
    assert chosen == []


def test_http_logs_public_endpoint(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    caplog.set_level(logging.INFO)
    settings = Settings.model_validate(
        {
            "transport": "http",
            "public_url": "https://example.ngrok-free.app",
            "auth_mode": "bearer",
            "auth_token": TOKEN,
        }
    )
    cli.run_http(settings)
    assert "https://example.ngrok-free.app/mcp" in caplog.text


def server_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("MCP_")}
    return env | extra


@pytest.mark.anyio
async def test_stdio_end_to_end() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server_template"], env=server_env())
    async with Client(params) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
    assert "5" in result.content[0].text  # type: ignore[union-attr]


def test_stdio_stdout_is_pure_jsonrpc_and_exits_cleanly_on_eof() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_server_template"],
        input=json.dumps(INITIALIZE) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
        env=server_env(MCP_LOG_LEVEL="DEBUG"),
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines
    for line in lines:
        assert json.loads(line)["jsonrpc"] == "2.0"


def test_http_server_stops_on_sigterm() -> None:
    port = "8765"
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server_template", "--transport", "http"],
        env=server_env(MCP_PORT=port),
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                if httpx2.get(f"http://127.0.0.1:{port}/healthz").status_code == 200:
                    break
            except httpx2.TransportError:
                pass
            assert time.monotonic() < deadline, "server did not become healthy"
            time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=15) == 0
    finally:
        proc.kill()
