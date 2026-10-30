"""HTTP authentication: static bearer token and OAuth 2.1 resource server (JWT) modes."""

import hmac
import json
import logging
from typing import Any

import anyio.to_thread
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server_template.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_JWT_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]


class StaticTokenVerifier(TokenVerifier):
    """Accepts exactly one shared secret."""

    def __init__(self, expected: str):
        self._expected = expected.encode()

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token.encode(), self._expected):
            return AccessToken(token=token, client_id="bearer", scopes=[])
        return None


class JWTTokenVerifier(TokenVerifier):
    """Validates JWT access tokens signed by a key from the authorization server's JWKS."""

    def __init__(self, *, issuer: str, jwks_url: str, audience: str):
        self._issuer = issuer
        self._audience = audience
        self._jwks = jwt.PyJWKClient(jwks_url, cache_keys=True)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            # PyJWKClient fetches over blocking HTTP, so keep it off the event loop.
            claims = await anyio.to_thread.run_sync(self._decode, token)
        except jwt.PyJWTError as exc:
            logger.info("Rejected access token: %s", type(exc).__name__)
            return None
        scope = claims.get("scope", claims.get("scp", []))
        scopes = scope.split() if isinstance(scope, str) else list(scope)
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or claims.get("azp") or claims.get("sub", "unknown")),
            scopes=scopes,
            expires_at=claims.get("exp"),
            resource=self._audience,
            subject=claims.get("sub"),
            claims={"iss": claims.get("iss")},
        )

    def _decode(self, token: str) -> dict[str, Any]:
        signing_key = self._jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            issuer=self._issuer,
            audience=self._audience,
            leeway=30,
            options={"require": ["exp", "iss", "aud"]},
        )


def oauth_components(settings: Settings) -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Verifier and SDK auth settings for oauth mode; (None, None) otherwise."""
    if settings.auth_mode != "oauth":
        return None, None
    assert settings.oauth_issuer and settings.oauth_jwks_url and settings.oauth_resource_url  # checked by Settings
    verifier = JWTTokenVerifier(
        issuer=settings.oauth_issuer, jwks_url=settings.oauth_jwks_url, audience=settings.oauth_resource_url
    )
    # Validate from strings: AuthSettings keeps path-less URLs exact (no added trailing slash),
    # which matters because clients compare the issuer by exact string match (RFC 8414).
    auth = AuthSettings.model_validate(
        {
            "issuer_url": settings.oauth_issuer,
            "resource_server_url": settings.oauth_resource_url,
            "required_scopes": settings.oauth_required_scopes or None,
            # JWTTokenVerifier already checks the audience.
            "validate_token_resource": False,
        }
    )
    return verifier, auth


class BearerTokenMiddleware:
    """Requires `Authorization: Bearer <MCP_AUTH_TOKEN>` on the MCP endpoint only."""

    def __init__(self, app: ASGIApp, *, token: str, path: str):
        self.app = app
        self.path = path
        self.verifier = StaticTokenVerifier(token)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_protected(scope["path"]):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        header = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and await self.verifier.verify_token(token.strip()):
            await self.app(scope, receive, send)
            return
        logger.info("Rejected MCP request: %s bearer token", "invalid" if header else "missing")
        await _send_401(send, invalid=bool(header))

    def _is_protected(self, path: str) -> bool:
        return path == self.path or path.startswith(self.path.rstrip("/") + "/")


async def _send_401(send: Send, *, invalid: bool) -> None:
    challenge = 'Bearer error="invalid_token"' if invalid else "Bearer"
    body = json.dumps({"error": "invalid_token", "error_description": "Authentication required"}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", challenge.encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
