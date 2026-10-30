## Context

The repository is empty apart from OpenSpec scaffolding (see proposal.md - Why). The user chose Python, both stdio and Streamable HTTP transports, and all optional extras (example primitives, tests/lint/CI, Dockerfile, HTTP auth). Requirements are in `specs/`; this document covers how to meet them.

The primary users are hackathon students who run the server on their own laptops and connect it to a SaaS telephony Voice AI web application. That application calls the MCP server from the cloud, so the laptop must be reachable from the public internet, and ngrok is the chosen tunnel. Production deployment (Docker, OAuth) stays supported, but the hackathon path must be the shortest one.

Constraints:
- MCP over stdio reserves stdout for JSON-RPC, so nothing else may write to it.
- A tunnel forwards public traffic to `127.0.0.1`, so "bound to loopback" no longer means "private".
- Recent `mcp` SDK versions turn on DNS-rebinding protection (a Host header allowlist) when the server binds to localhost, so requests carrying the ngrok hostname are rejected unless that host is allowed.
- The MCP authorization spec has HTTP servers act as OAuth 2.1 **resource servers**: they validate tokens and publish RFC 9728 Protected Resource Metadata, but they do not issue tokens.
- Tests must run offline (no real identity provider and no network).

## Goals / Non-Goals

**Goals:**
- A small, readable codebase that is easy to fork and rename.
- One server factory used by both transports and by the tests, so behavior is the same everywhere.
- Auth is applied only at the HTTP edge; primitives never know about it.
- A student goes from clone to "the Voice AI web app calls my tool" with only the quick-start guide.

**Non-Goals:**
- Running an authorization server, issuing tokens, or Dynamic Client Registration.
- Horizontal scaling and session affinity for stateful HTTP sessions (we keep the SDK default of stateful sessions; see Risks).
- Publishing the image to a registry or the package to PyPI.
- Per-tool authorization based on token claims (only global required scopes).
- Paid ngrok features (custom domains, traffic policies, no interstitial page), and enforcing auth at the ngrok edge; the server does its own auth.
- Automating ngrok from Python (e.g. the `ngrok` SDK). Students run the ngrok CLI in a second terminal, which keeps the template free of ngrok dependencies.
- Product-specific screenshots of the Voice AI web application; the guide names the exact field values instead.

## Decisions

### D1. Use the official `mcp` SDK's FastMCP API
FastMCP's decorator API (`@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()`) generates input schemas from type hints, and the SDK ships the stdio and Streamable HTTP transports plus resource-server auth hooks.
- *Alternative:* the standalone `fastmcp` 2.x package. It has more features, but it is a third-party dependency with a larger surface area; the official SDK is enough for a template.
- *Alternative:* the low-level `mcp.server.Server`. It needs much more boilerplate and is a worse starting point to copy from.

### D2. Package layout and server factory
```
src/mcp_server_template/
  __init__.py        # __version__ from package metadata
  __main__.py        # `python -m mcp_server_template` -> cli.main()
  cli.py             # arg parsing, logging setup, transport dispatch
  config.py          # Settings (pydantic-settings, env prefix MCP_)
  server.py          # create_server(settings) -> FastMCP
  auth.py            # token verifiers + HTTP auth wiring
  http_app.py        # build_http_app(settings) -> ASGI app (MCP + /healthz)
  tools.py           # register(mcp): example `add`
  resources.py       # register(mcp): info://server, greeting://{name}
  prompts.py         # register(mcp): code_review
```
`create_server(settings)` builds a fresh FastMCP instance and calls `tools.register`, `resources.register` and `prompts.register`. Each module defines its decorated functions inside `register(mcp)`, so adding a primitive only means editing that module (example-primitives: registration convention).
- *Alternative:* a module-level global `mcp = FastMCP(...)`. It is the shortest option, but tests can't build servers with different settings, and import order becomes fragile.

The console script is `mcp-server-template = mcp_server_template.cli:main`. Renaming the template means a find-and-replace of `mcp_server_template` / `mcp-server-template`, which the README documents.

### D3. Configuration with pydantic-settings
`Settings` is a `BaseSettings` subclass with `env_prefix="MCP_"` and `env_file=".env"`, and `transport`/`auth_mode` are typed as `Literal` enums. Cross-field rules live in a `model_validator`: the settings required for the chosen auth mode, the minimum bearer-token length (32), and refusing `auth_mode=none` when the server is publicly exposed (non-loopback bind **or** `public_url` set) unless `allow_insecure`. That way every misconfiguration fails in one place, before any socket opens. `cli.main` catches `ValidationError`, prints a concise message to stderr, and exits 2.
- *Alternative:* hand-rolled `os.environ` parsing. It means more code, weaker error messages, and no type coercion.

| Variable | Default | Notes |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `http`; `--transport` overrides |
| `MCP_HOST` / `MCP_PORT` / `MCP_HTTP_PATH` | `127.0.0.1` / `8000` / `/mcp` | HTTP only |
| `MCP_PUBLIC_URL` | — | public base URL (e.g. ngrok dev domain); adds its host to allowed hosts |
| `MCP_LOG_LEVEL` | `INFO` | |
| `MCP_AUTH_MODE` | `none` | `none` \| `bearer` \| `oauth` |
| `MCP_ALLOW_INSECURE` | `false` | allow `none` on non-loopback bind |
| `MCP_AUTH_TOKEN` | — | `SecretStr`, bearer mode |
| `MCP_OAUTH_ISSUER` / `MCP_OAUTH_JWKS_URL` / `MCP_OAUTH_RESOURCE_URL` | — | oauth mode |
| `MCP_OAUTH_REQUIRED_SCOPES` | empty | comma-separated |

Secrets use `SecretStr` so they never show up in reprs or logs.

### D4. HTTP app assembly
`build_http_app(settings)` takes FastMCP's Streamable HTTP ASGI app (served at `MCP_HTTP_PATH`) and adds `GET /healthz` as an unauthenticated custom route. `cli` runs the app with `uvicorn.run(...)`, whose own signal handling covers graceful shutdown on SIGINT/SIGTERM. Building the ASGI app ourselves, instead of calling `mcp.run("streamable-http")`, lets the tests drive exactly the production app in-process through `httpx.ASGITransport`.

**Host validation:** `create_server` passes the SDK's transport-security settings explicitly instead of relying on its localhost auto-defaults. DNS-rebinding protection stays on, and `allowed_hosts` contains `localhost:*`, `127.0.0.1:*` and, when `MCP_PUBLIC_URL` is set, its host. `allowed_origins` gets the matching origins. Because the hosts are explicit, a tunnel works without turning the protection off.
- *Alternative:* disable DNS-rebinding protection. That's simpler, but it removes a real defense for laptops on hackathon Wi-Fi.
- *Alternative:* a separate `MCP_ALLOWED_HOSTS` list. It's more flexible, but students would have to keep two values in sync. Deriving the host from `MCP_PUBLIC_URL` means one value, which the guide and the startup log reuse.

### D5. Auth: one `TokenVerifier` abstraction, two implementations
Both auth modes implement the SDK's `TokenVerifier` protocol (`verify_token(token) -> AccessToken | None`):
- **`StaticTokenVerifier`** compares the token with `MCP_AUTH_TOKEN` using `hmac.compare_digest`.
- **`JWTTokenVerifier`** uses PyJWT with `PyJWKClient(jwks_url)`, which caches keys and refetches on an unknown `kid`. It checks the signature (asymmetric algorithms only, `RS256`/`ES256`; `none` and HS* are rejected), `iss`, `aud` (must contain the resource URL), and `exp`/`nbf` with a small leeway. Scopes come from the `scope` (space-separated) or `scp` claims.

In `oauth` mode the verifier is passed to FastMCP together with `AuthSettings(issuer_url, resource_server_url, required_scopes)`. The SDK then adds the bearer-auth middleware (401/403 with `WWW-Authenticate` and `resource_metadata`) and serves `/.well-known/oauth-protected-resource`.

`bearer` mode has no authorization server, so it must not advertise Protected Resource Metadata. It therefore uses a small Starlette middleware in `auth.py` that wraps only the MCP path, calls `StaticTokenVerifier`, and returns 401 with `WWW-Authenticate: Bearer`.
- *Alternative:* one custom middleware for both modes, ignoring the SDK's auth support. This gives full control, but it duplicates spec-sensitive logic (header formats, metadata) that the SDK already maintains.
- *Alternative:* `authlib` or `python-jose` for JWT. `python-jose` is poorly maintained, and `authlib` is heavier than we need for verification only.

`/healthz` and the metadata endpoint sit outside the protected MCP route, so they stay reachable without credentials.

### D6. Logging
`cli` configures the root logger with a `StreamHandler(sys.stderr)` before the server is built, and also routes uvicorn's loggers to stderr. Bearer tokens are never logged; auth failures log only the reason (e.g. `expired`, `bad audience`).

### D7. Testing strategy
- **Primitives:** in-memory client/server pairs from the SDK's memory-transport helpers, run against `create_server(settings)`. These are fast and need no ports.
- **HTTP + auth:** `httpx.AsyncClient(transport=ASGITransport(build_http_app(settings)))`. OAuth tests generate an RSA key pair in a fixture, serve the matching JWKS by monkeypatching the `PyJWKClient` fetch, and mint tokens with PyJWT covering valid, expired, wrong issuer, wrong audience, bad signature and missing scope. No network is used.
- **stdio end-to-end:** launch `python -m mcp_server_template` as a subprocess through the SDK's stdio client, call `add`, and assert that a clean shutdown happens on EOF.
- **Config:** unit tests for defaults, env precedence, and each validation error.
- Async tests use the `anyio` pytest plugin, which ships with the SDK's dependency `anyio`, instead of `pytest-asyncio`.

### D8. Tooling
`uv` handles dependencies and the lockfile (`uv sync --locked`). `ruff` handles both lint and format, replacing black, isort and flake8. `mypy --strict` covers `src/` and `tests/`. The target is Python ≥3.12; CI tests 3.12 and 3.13. The documented commands are `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`.

### D9. Container
A multi-stage Dockerfile:
1. **Builder:** `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` runs `uv sync --locked --no-dev --no-editable` into `/app/.venv`, using a cache mount.
2. **Runtime:** `python:3.12-slim-bookworm`. It copies only `/app/.venv`, creates an unprivileged `app` user, and sets `ENV MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT=8000`, `EXPOSE 8000`, `USER app`, and `CMD ["mcp-server-template"]`.

The `HEALTHCHECK` uses a short `python -c "urllib.request.urlopen(...)"` because slim images have no curl. A `.dockerignore` excludes `.git`, `.env*` (except `.env.example`), `tests`, `.venv`, caches and `openspec/`. Because the image binds to `0.0.0.0`, the insecure-bind guard (D3) forces deployers to configure auth.

### D10. CI
`.github/workflows/ci.yml` runs on `push` to `main` and on `pull_request`.
- The `check` job uses `astral-sh/setup-uv` with a Python 3.12/3.13 matrix and runs `uv sync --locked`, then ruff check, ruff format check, mypy and pytest.
- The `docker` job runs `docker build` (no push). It then smoke-tests the image: run it with bearer auth, poll `/healthz`, and fail if it never turns healthy.

### D11. ngrok as the hackathon tunnel
The quick-start guide (`docs/quickstart-ngrok.md`) uses the ngrok CLI on the free plan with the account's assigned **dev domain**: `ngrok http 8000` (the free plan always uses the assigned domain; `--url` with any other name fails). The URL stays the same across restarts, so each student configures the Voice AI web application once. The free plan's terms set no development-only or non-commercial restriction; the relevant constraints are its quotas (about 20k HTTP requests and 1 GB out per month, 3 endpoints, 1 user per account) and the 18+ age requirement.
- *Alternative:* SSH tunnels (localhost.run, Pinggy, Serveo). They need no install, but the free URLs change on reconnect (Pinggy's also expire after 60 min), so the web app would need reconfiguring constantly during a hackathon.
- *Alternative:* Cloudflare Quick Tunnel. It needs no account, but the URL is random per run and quick tunnels have streaming limitations.
- *Alternative:* Tailscale Funnel. It has a stable URL, but it's more setup (tailnet, Funnel enablement) for students than ngrok.

The free plan shows an interstitial warning page only to browser traffic. The Voice AI platform calls the server from its backend, so it isn't affected. The guide's troubleshooting table covers the `ngrok-skip-browser-warning` header in case a browser-based test hits the page.

### D12. Guide is a separate short doc, verified for real
The guide lives in its own file instead of a README section, so it stays at most one page and can be printed or shared on its own. The README stays the complete reference and links to the guide in its first lines. Docs aren't unit-testable, so task 9 has someone follow the guide on a clean machine against a real ngrok account and the Voice AI web app before the change is considered done.

## Risks / Trade-offs

- **[Risk] SDK auth internals change between versions** (the `AuthSettings`/`TokenVerifier` API or the exact `WWW-Authenticate` format). → The http-auth tests assert the observable HTTP behavior from the spec, not SDK internals, so an SDK upgrade that breaks the contract fails CI. Pin a compatible `mcp` version range in `pyproject.toml`.
- **[Risk] The SDK's metadata or 403 behavior doesn't fully match the spec** (e.g. `scopes_supported` is missing). → Tests would catch it; fall back to adding the missing piece in `auth.py` (custom metadata route or middleware) rather than changing the spec.
- **[Trade-off] Stateful Streamable HTTP sessions** need sticky routing when running multiple replicas. → Documented in the README; switching to the SDK's stateless mode is a one-line change for forks that don't need server-initiated requests.
- **[Risk] JWKS endpoint unavailable** at token-validation time. → `PyJWKClient` caches keys, so an outage only affects unknown `kid`s; those requests fail closed with 401.
- **[Trade-off] The static bearer token is a shared secret** with no rotation or per-client identity. → Documented as suitable for internal or single-tenant use only; `oauth` is recommended for anything multi-user.
- **[Risk] Students expose an unauthenticated server through the tunnel.** → Setting `MCP_PUBLIC_URL` together with auth `none` refuses to start, short tokens are rejected, and the guide generates a strong token.
- **[Risk] A team shares one ngrok account and hits free-plan quotas or the endpoint limit mid-demo.** → The guide says each participant uses their own account; troubleshooting covers the limit errors.
- **[Risk] Participants under 18 can't accept ngrok's terms.** → The guide notes the requirement. Organizers should check participant ages, and the README lists localhost.run as an unsupported, no-account fallback (`MCP_PUBLIC_URL` works with any tunnel).
- **[Risk] The Voice AI web application doesn't support a custom `Authorization` header.** → Assumed supported. If not, the bearer mode would need a token-in-path option; confirm with the platform before implementation (see Open Questions).
- **[Risk] Voice calls are latency-sensitive**, and a laptop behind a tunnel adds round-trip time. → The example tools are trivial; the README advises keeping tool calls fast and avoiding long-running work in tools.
- **[Risk] A stray `print()` in a primitive corrupts the stdio stream.** → The README warns about it, the stdio end-to-end test would catch it in the examples, and ruff's `T20` rule (flake8-print) is enabled for `src/`.

## Open Questions

- Exact field names in the Voice AI web application's MCP settings (server URL, custom headers). The guide uses generic labels until these are confirmed; this doesn't change the server behavior.
