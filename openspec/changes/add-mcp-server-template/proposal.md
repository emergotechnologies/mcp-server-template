## Why

A team of students will use this repository at a hackathon to build MCP servers for a SaaS telephony Voice AI solution. The SaaS web application connects to an MCP server by URL, so each student's server must be reachable from the public internet while it runs on their own laptop. Without a template, every team would rebuild the transport wiring, auth and tunnel setup, losing hackathon time and probably exposing an unauthenticated server. This repository is empty today. A ready-made Python template with a short, precise "run locally + expose with ngrok" guide lets students get a working connection quickly and spend their time on their own tools.

## What Changes

- Add a Python package (`mcp_server_template`) built on the official `mcp` Python SDK (FastMCP API), managed with `uv`.
- Provide a single entry point that runs the server over **stdio** (for local clients such as Claude Code/Desktop) or **Streamable HTTP** (for remote deployment), selected by CLI flag or environment variable.
- Centralize configuration in typed settings loaded from environment variables / `.env`, with safe defaults.
- Ship one worked example of each MCP primitive — a **tool**, a **resource** (static and templated), and a **prompt** — plus a clear registration pattern to copy when adding new ones.
- Protect the HTTP transport with pluggable authentication: `none` (local dev only), static **bearer token**, or **OAuth 2.1 resource server** mode that validates JWT access tokens and publishes Protected Resource Metadata as the MCP authorization spec requires.
- Add an unauthenticated `/healthz` endpoint for HTTP deployments.
- Add an `MCP_PUBLIC_URL` setting for the externally reachable URL (e.g. the ngrok domain). The server accepts requests for that host while keeping DNS-rebinding protection, and refuses to start with auth disabled when a public URL is set.
- Add a short, precise **quick-start guide** for hackathon participants: run the server locally, expose it with **ngrok** (free plan, stable dev domain), verify it, and configure it in the Voice AI web application with a bearer token.
- Add developer tooling: `pytest` unit and in-memory integration tests, `ruff` (lint + format), type checking, and a GitHub Actions CI workflow running all of them.
- Add a multi-stage `Dockerfile` that runs the server over Streamable HTTP as a non-root user.
- Add a README covering quick start, configuration, connecting from Claude Code, adding primitives, and deployment.

## Capabilities

### New Capabilities
- `server-runtime`: Server startup, transport selection (stdio / Streamable HTTP), configuration loading, public URL / allowed hosts, logging, and health endpoint.
- `example-primitives`: The example tool, resources and prompt, and the convention for registering new primitives.
- `http-auth`: Authentication for the Streamable HTTP transport (none / bearer token / OAuth 2.1 JWT resource server), including Protected Resource Metadata.
- `container-image`: The Docker image used to deploy the server over HTTP.
- `developer-tooling`: Test suite, lint/format/type-check commands, the CI workflow that enforces them, the README, and the ngrok quick-start guide.

### Modified Capabilities
<!-- None: the repository has no existing specs. -->

## Impact

- **New code**: `src/mcp_server_template/`, `tests/`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, `.env.example`, `README.md`, `docs/quickstart-ngrok.md`.
- **Dependencies**: `mcp` (official SDK, includes Starlette/uvicorn), `pydantic-settings`, `pyjwt[crypto]` (OAuth mode); dev: `pytest`, `httpx`, `ruff`, `mypy` (async tests use the `anyio` pytest plugin).
- **Runtime requirement**: Python 3.12+, `uv`.
- **External systems**: The quick start depends on ngrok (free account per participant, 18+ per ngrok's terms) and on the Voice AI web application accepting an MCP server URL plus an `Authorization` header. OAuth mode depends on an external authorization server (issuer + JWKS URL) supplied by the deployer; the template does not include an authorization server.
