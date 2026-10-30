"""Runtime settings, loaded from `MCP_*` environment variables and an optional `.env` file."""

import ipaddress
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_TOKEN_LENGTH = 32
TOKEN_HINT = "python -c 'import secrets; print(secrets.token_urlsafe(32))'"  # noqa: S105 - a command, not a secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    http_path: str = "/mcp"
    public_url: str | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    auth_mode: Literal["none", "bearer", "oauth"] = "none"
    allow_insecure: bool = False
    auth_token: SecretStr | None = None
    oauth_issuer: str | None = None
    oauth_jwks_url: str | None = None
    oauth_resource_url: str | None = None
    oauth_required_scopes: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("http_path")
    @classmethod
    def _path_starts_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("must start with '/'")
        return value.rstrip("/") or "/"

    @field_validator("public_url", "oauth_issuer", "oauth_jwks_url", "oauth_resource_url")
    @classmethod
    def _absolute_http_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("must be an absolute http(s) URL, e.g. https://example.ngrok-free.app")
        return value.rstrip("/")

    @field_validator("oauth_required_scopes", mode="before")
    @classmethod
    def _split_scopes(cls, value: object) -> object:
        if isinstance(value, str):
            return [scope.strip() for scope in value.split(",") if scope.strip()]
        return value

    @model_validator(mode="after")
    def _check_auth(self) -> Self:
        if self.auth_mode == "bearer":
            token = self.auth_token.get_secret_value() if self.auth_token else ""
            if not token:
                raise ValueError(
                    f"MCP_AUTH_TOKEN is required when MCP_AUTH_MODE=bearer. Generate one with: {TOKEN_HINT}"
                )
            if len(token) < MIN_TOKEN_LENGTH:
                raise ValueError(
                    f"MCP_AUTH_TOKEN must be at least {MIN_TOKEN_LENGTH} characters. Generate one with: {TOKEN_HINT}"
                )
        if self.auth_mode == "oauth":
            for name in ("oauth_issuer", "oauth_jwks_url", "oauth_resource_url"):
                if not getattr(self, name):
                    raise ValueError(f"MCP_{name.upper()} is required when MCP_AUTH_MODE=oauth")
        if (
            self.transport == "http"
            and self.auth_mode == "none"
            and self.is_publicly_exposed
            and not self.allow_insecure
        ):
            raise ValueError(
                "MCP_AUTH_MODE=none is refused because the server is publicly reachable "
                "(non-loopback MCP_HOST or MCP_PUBLIC_URL set). Set MCP_AUTH_MODE=bearer and MCP_AUTH_TOKEN "
                f"(generate one with: {TOKEN_HINT}), or MCP_ALLOW_INSECURE=true if you really mean it."
            )
        return self

    @property
    def is_publicly_exposed(self) -> bool:
        """True when the server binds beyond loopback or is reachable through a tunnel/proxy."""
        return self.public_url is not None or not _is_loopback(self.host)

    @property
    def public_endpoint(self) -> str | None:
        return f"{self.public_url}{self.http_path}" if self.public_url else None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
