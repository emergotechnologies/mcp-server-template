from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from mcp_server_template.config import Settings

TOKEN = "t" * 32


def test_defaults() -> None:
    settings = Settings()
    assert settings.transport == "stdio"
    assert (settings.host, settings.port, settings.http_path) == ("127.0.0.1", 8000, "/mcp")
    assert settings.auth_mode == "none"
    assert settings.public_url is None


def test_env_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("MCP_PORT=9000\nMCP_LOG_LEVEL=DEBUG\n")
    monkeypatch.setenv("MCP_PORT", "9100")
    settings = Settings()
    assert settings.port == 9100
    assert settings.log_level == "DEBUG"


def test_scopes_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_OAUTH_REQUIRED_SCOPES", "mcp:read, mcp:write")
    assert Settings().oauth_required_scopes == ["mcp:read", "mcp:write"]


def test_public_endpoint() -> None:
    settings = Settings(
        transport="http", public_url="https://example.ngrok-free.app/", auth_mode="bearer", auth_token=SecretStr(TOKEN)
    )
    assert settings.public_endpoint == "https://example.ngrok-free.app/mcp"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"MCP_PORT": "not-a-number"}, "port"),
        ({"MCP_TRANSPORT": "carrier-pigeon"}, "transport"),
        ({"MCP_PUBLIC_URL": "example.ngrok-free.app"}, "public_url"),
        ({"MCP_AUTH_MODE": "bearer"}, "MCP_AUTH_TOKEN"),
        ({"MCP_AUTH_MODE": "bearer", "MCP_AUTH_TOKEN": "secret"}, "MCP_AUTH_TOKEN"),
        ({"MCP_AUTH_MODE": "oauth"}, "MCP_OAUTH_ISSUER"),
        (
            {
                "MCP_AUTH_MODE": "oauth",
                "MCP_OAUTH_ISSUER": "https://issuer.example",
                "MCP_OAUTH_RESOURCE_URL": "https://x/mcp",
            },
            "MCP_OAUTH_JWKS_URL",
        ),
        ({"MCP_TRANSPORT": "http", "MCP_HOST": "0.0.0.0"}, "MCP_AUTH_MODE=none is refused"),  # noqa: S104
        (
            {"MCP_TRANSPORT": "http", "MCP_PUBLIC_URL": "https://example.ngrok-free.app"},
            "MCP_AUTH_MODE=none is refused",
        ),
    ],
)
def test_invalid_settings_name_the_variable(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: str
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert expected in str(excinfo.value)


def test_short_token_error_shows_generator() -> None:
    with pytest.raises(ValidationError, match=r"secrets\.token_urlsafe"):
        Settings(auth_mode="bearer", auth_token=SecretStr("secret"))


def test_insecure_override_allows_public_bind() -> None:
    settings = Settings(transport="http", host="0.0.0.0", allow_insecure=True)  # noqa: S104
    assert settings.is_publicly_exposed


def test_stdio_ignores_public_bind_rule() -> None:
    assert Settings(transport="stdio", host="0.0.0.0").auth_mode == "none"  # noqa: S104


def test_env_example_documents_every_setting() -> None:
    example = (Path(__file__).parent.parent / ".env.example").read_text()
    for name in Settings.model_fields:
        assert f"MCP_{name.upper()}=" in example, f"MCP_{name.upper()} missing from .env.example"
