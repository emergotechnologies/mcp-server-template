## 1. Project setup

- [x] 1.1 Create `pyproject.toml` (name `mcp-server-template`, Python ≥3.12, `src/` layout, console script `mcp-server-template`, deps `mcp` with a pinned compatible range, `pydantic-settings`, `pyjwt[crypto]`; dev group `pytest`, `httpx`, `ruff`, `mypy`) and verify `uv sync` succeeds and writes `uv.lock`
- [x] 1.2 Configure ruff (lint rules incl. `T20` for `src/`, formatter) and `mypy --strict` and pytest (anyio plugin) in `pyproject.toml`; verify `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy` run cleanly on the empty package
- [x] 1.3 Add `.gitignore` (venv, caches, `.env`) and verify `git status` does not show `.venv/` or `__pycache__/`

## 2. Configuration

- [x] 2.1 Implement `config.py` `Settings` with all `MCP_` variables, defaults and `SecretStr` secrets per design D3; verify unit tests for defaults and env/`.env` precedence pass
- [x] 2.2 Add cross-field validation (transport values, `MCP_PUBLIC_URL` format, required settings per auth mode, bearer token ≥32 chars with a token-generation hint, refusing auth `none` when publicly exposed (non-loopback bind or `MCP_PUBLIC_URL` set) unless `MCP_ALLOW_INSECURE`); verify a unit test per error case asserts the offending variable is named
- [x] 2.3 Add `.env.example` documenting every setting; verify a test asserts every `Settings` field appears in `.env.example`

## 3. Server core and primitives

- [x] 3.1 Implement `server.py` `create_server(settings)` returning a FastMCP instance named `mcp-server-template` with version from package metadata; verify an in-memory client `initialize` returns that name and version
- [x] 3.2 Implement `tools.py` with `add(a, b)`; verify in-memory tests for listing, correct sum (2+3=5) and invalid-argument error
- [x] 3.3 Implement `resources.py` with `info://server` (JSON name/version) and `greeting://{name}`; verify in-memory tests for list, templates/list and reads
- [x] 3.4 Implement `prompts.py` with `code_review(code)`; verify in-memory tests for list, rendered message containing the code, and missing-argument error

## 4. CLI, logging and stdio transport

- [x] 4.1 Implement `cli.py` (`--transport` overriding `MCP_TRANSPORT`, stderr logging at `MCP_LOG_LEVEL`, validation errors printed to stderr with exit code 2) and `__main__.py`; verify unit tests for precedence and invalid-transport exit
- [x] 4.2 Wire the stdio transport; verify an end-to-end test launching `python -m mcp_server_template` via the SDK stdio client calls `add`, sees only JSON-RPC on stdout, and the process exits 0 on EOF

## 5. Streamable HTTP transport

- [x] 5.1 Implement `http_app.py` `build_http_app(settings)` mounting MCP at `MCP_HTTP_PATH` plus unauthenticated `GET /healthz`; verify ASGI tests for `/healthz` 200 and an MCP `initialize` + `add` call over HTTP with auth `none`
- [x] 5.2 Configure the SDK's transport security explicitly (DNS-rebinding protection on; allowed hosts/origins = localhost, 127.0.0.1, plus the `MCP_PUBLIC_URL` host) per design D4; verify ASGI tests: `Host: example.ngrok-free.app` accepted when it's the public URL, unknown host rejected with 4xx, localhost accepted
- [x] 5.3 Log the public MCP endpoint (`MCP_PUBLIC_URL` + path) at HTTP startup; verify a test captures it in the log output
- [x] 5.4 Run the HTTP app via uvicorn from `cli.py` on `MCP_HOST`/`MCP_PORT` with uvicorn logs on stderr; verify manually that `uv run mcp-server-template --transport http` serves `/healthz` and exits 0 on Ctrl+C

## 6. HTTP authentication

- [x] 6.1 Implement `StaticTokenVerifier` and bearer-mode middleware around the MCP route only; verify ASGI tests: valid token → 200, missing/wrong token → 401 with `WWW-Authenticate: Bearer`, `/healthz` open
- [x] 6.2 Implement `JWTTokenVerifier` (PyJWT + `PyJWKClient`, asymmetric algs only, iss/aud/exp/nbf, `scope`/`scp` parsing); verify unit tests with a fixture RSA key covering valid, expired, wrong issuer, wrong audience, bad signature and `alg=none` rejection
- [x] 6.3 Wire oauth mode via FastMCP `AuthSettings` + verifier; verify ASGI tests: valid token → 200, invalid → 401 with `error="invalid_token"` and `resource_metadata`, missing scope → 403 `insufficient_scope`, no token → 401 with `resource_metadata`
- [x] 6.4 Verify `GET /.well-known/oauth-protected-resource` returns `resource`, `authorization_servers` and `scopes_supported` without auth; if the SDK's output deviates from the spec, add the missing behavior in `auth.py` until the test passes
- [x] 6.5 Verify tokens never appear in logs with a test that captures log output during failed and successful auth

## 7. Container image

- [x] 7.1 Write the multi-stage `Dockerfile` (uv builder → slim runtime, non-root `app` user, HTTP env defaults, `EXPOSE 8000`, `HEALTHCHECK` on `/healthz`) and `.dockerignore`; verify `docker build .` succeeds
- [x] 7.2 Verify the image: run with bearer auth and confirm `/healthz` 200, container reports healthy, `docker exec ... id -u` is non-zero, no `.env` in the image; run without auth settings and confirm non-zero exit with an explanatory error

## 8. CI

- [x] 8.1 Add `.github/workflows/ci.yml` with the `check` job (setup-uv, Python 3.12/3.13 matrix, `uv sync --locked`, ruff check, ruff format check, mypy, pytest); verify locally that each command passes
- [x] 8.2 Add the `docker` job (build + bearer-auth run + `/healthz` smoke check); verify the workflow is valid YAML and the smoke-check script passes locally against the built image

## 9. Documentation and final verification

- [x] 9.1 Write `README.md` covering every item in the developer-tooling documentation requirement, with a link to the ngrok quick start in its first lines, `claude mcp add` examples for stdio and HTTP, the auth modes, how to rename the template, the stateful-session scaling note, keeping tool calls fast for voice latency, and localhost.run as an unsupported no-account fallback; verify each documented command was run successfully
- [x] 9.2 Write `docs/quickstart-ngrok.md` per the quick-start guide requirement (≤8 numbered steps, copy-pasteable commands, troubleshooting table); verify it has at most 8 steps and fits on one printed page
- [ ] 9.3 Follow `docs/quickstart-ngrok.md` on a clean clone with a real free ngrok account: verify step 7's curl results (healthz 200, authenticated initialize OK, unauthenticated 401), and that the Voice AI web application lists and calls `add` through the ngrok URL; fix the guide wherever a step deviated
- [ ] 9.4 Run the full check suite (`ruff check`, `ruff format --check`, `mypy`, `pytest`, `docker build`) on a clean checkout and verify all pass; then connect the server to Claude Code over stdio and confirm `add` is callable
- [x] 9.5 Run `openspec validate add-mcp-server-template --strict` and verify it passes
