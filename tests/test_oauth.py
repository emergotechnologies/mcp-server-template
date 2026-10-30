import json
import time
from collections.abc import Iterator
from typing import Any

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mcp_server_template.auth import JWTTokenVerifier
from mcp_server_template.config import Settings
from mcp_server_template.http_app import build_http_app

from .conftest import serve
from .test_http import initialize

ISSUER = "https://auth.example.com"
JWKS_URL = "https://auth.example.com/.well-known/jwks.json"
RESOURCE = "https://mcp.example.com/mcp"
KID = "test-key"

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def _fake_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the test public key instead of fetching the JWKS over the network."""
    jwk = json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key())) | {"kid": KID, "use": "sig", "alg": "RS256"}
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [jwk]})


def make_token(*, key: Any = PRIVATE_KEY, algorithm: str = "RS256", **overrides: Any) -> str:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": RESOURCE, "sub": "user-1", "exp": now + 300, "iat": now, "scope": "mcp:tools"}
    claims |= overrides
    payload = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": KID})


def verifier() -> JWTTokenVerifier:
    return JWTTokenVerifier(issuer=ISSUER, jwks_url=JWKS_URL, audience=RESOURCE)


@pytest.mark.anyio
async def test_valid_token() -> None:
    access = await verifier().verify_token(make_token())
    assert access is not None
    assert access.scopes == ["mcp:tools"]
    assert access.subject == "user-1"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: make_token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(lambda: make_token(iss="https://evil.example.com"), id="wrong-issuer"),
        pytest.param(lambda: make_token(aud="https://other.example.com/mcp"), id="wrong-audience"),
        pytest.param(lambda: make_token(key=OTHER_KEY), id="bad-signature"),
        pytest.param(lambda: make_token(key=None, algorithm="none"), id="alg-none"),
        pytest.param(lambda: make_token(key="x" * 32, algorithm="HS256"), id="alg-hs256"),
        pytest.param(lambda: make_token(exp=None), id="no-exp"),
        pytest.param(lambda: "not-a-jwt", id="garbage"),
    ],
)
async def test_invalid_tokens_rejected(token: Any) -> None:
    assert await verifier().verify_token(token()) is None


@pytest.mark.anyio
async def test_scp_claim_list() -> None:
    access = await verifier().verify_token(make_token(scope=None, scp=["a", "b"]))
    assert access is not None
    assert access.scopes == ["a", "b"]


@pytest.fixture
def oauth_url() -> Iterator[str]:
    settings = Settings(
        transport="http",
        auth_mode="oauth",
        oauth_issuer=ISSUER,
        oauth_jwks_url=JWKS_URL,
        oauth_resource_url=RESOURCE,
        oauth_required_scopes=["mcp:tools"],
        public_url="https://mcp.example.com",
    )
    with serve(build_http_app(settings)) as url:
        yield url


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_oauth_valid_token(oauth_url: str) -> None:
    assert initialize(oauth_url, bearer(make_token())).status_code == 200


def test_oauth_invalid_token(oauth_url: str) -> None:
    response = initialize(oauth_url, bearer(make_token(exp=int(time.time()) - 3600)))
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert 'error="invalid_token"' in challenge
    assert "resource_metadata=" in challenge


def test_oauth_missing_token(oauth_url: str) -> None:
    response = initialize(oauth_url)
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_oauth_insufficient_scope(oauth_url: str) -> None:
    response = initialize(oauth_url, bearer(make_token(scope="other")))
    assert response.status_code == 403
    assert 'error="insufficient_scope"' in response.headers["www-authenticate"]


@pytest.mark.parametrize("path", ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"])
def test_protected_resource_metadata(oauth_url: str, path: str) -> None:
    response = httpx2.get(f"{oauth_url}{path}")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["resource"] == RESOURCE
    assert metadata["authorization_servers"] == [ISSUER]
    assert metadata["scopes_supported"] == ["mcp:tools"]


def test_oauth_leaves_healthz_open(oauth_url: str) -> None:
    assert httpx2.get(f"{oauth_url}/healthz").status_code == 200
