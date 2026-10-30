"""Builds the Streamable HTTP ASGI app: MCP endpoint, /healthz, auth and Host checks."""

from urllib.parse import urlsplit

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from mcp_server_template.auth import BearerTokenMiddleware
from mcp_server_template.config import Settings
from mcp_server_template.server import create_server

PROTECTED_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def build_http_app(settings: Settings, mcp: MCPServer | None = None) -> Starlette:
    mcp = mcp or create_server(settings)
    app = mcp.streamable_http_app(
        streamable_http_path=settings.http_path,
        transport_security=transport_security(settings),
    )
    app.router.routes.append(Route("/healthz", healthz, methods=["GET"]))
    if settings.auth_mode == "bearer":
        assert settings.auth_token is not None  # checked by Settings
        app.add_middleware(BearerTokenMiddleware, token=settings.auth_token.get_secret_value(), path=settings.http_path)
    if settings.auth_mode == "oauth":
        _add_root_metadata_route(app, settings)
    return app


async def healthz(request: Request) -> Response:
    """Liveness probe; never requires authentication."""
    return JSONResponse({"status": "ok"})


def transport_security(settings: Settings) -> TransportSecuritySettings:
    """DNS-rebinding protection that also accepts the public (tunnel) host."""
    hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if settings.public_url:
        public = urlsplit(settings.public_url)
        hosts.append(public.netloc)
        origins.append(f"{public.scheme}://{public.netloc}")
    return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins)


def _add_root_metadata_route(app: Starlette, settings: Settings) -> None:
    """The SDK serves RFC 9728 metadata at the path-suffixed URL; also serve it at the root well-known path."""
    assert settings.oauth_resource_url
    sdk_path = PROTECTED_RESOURCE_METADATA_PATH + urlsplit(settings.oauth_resource_url).path.rstrip("/")
    if sdk_path == PROTECTED_RESOURCE_METADATA_PATH:
        return  # the SDK route already is the root path
    sdk_route = next(r for r in app.router.routes if isinstance(r, Route) and r.path == sdk_path)
    app.router.routes.append(Route(PROTECTED_RESOURCE_METADATA_PATH, sdk_route.endpoint, methods=["GET", "OPTIONS"]))
