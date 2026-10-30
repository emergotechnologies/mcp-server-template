# MCP server template (Python)

> **Hackathon participants: start with the [quick-start guide](docs/quickstart-ngrok.md).** It takes you from clone to "the Voice AI web app calls my tool" in 8 steps.

A ready-to-fork [Model Context Protocol](https://modelcontextprotocol.io) server built on the official `mcp` Python SDK. It includes:

- **Transports:** stdio (local clients such as Claude Code) and Streamable HTTP (remote clients such as the Voice AI web application).
- **Example primitives:** one tool, two resources and one prompt to copy from.
- **HTTP auth:** a static bearer token, or an OAuth 2.1 resource server that validates JWTs and publishes RFC 9728 metadata.
- **Safe defaults:** the server refuses to run without auth when it's reachable from the internet, and keeps DNS-rebinding protection on even behind a tunnel.
- **Tooling and deployment:** tests, ruff, mypy, GitHub Actions CI and a Docker image.

## Prerequisites

Python 3.12+, [uv](https://docs.astral.sh/uv/), and optionally Docker and [ngrok](https://ngrok.com).

## Setup

```bash
uv sync
```

## Running

```bash
uv run mcp-server-template                    # stdio (default)
uv run mcp-server-template --transport http   # Streamable HTTP on http://127.0.0.1:8000/mcp
```

`--transport` overrides `MCP_TRANSPORT`. Over HTTP, `GET /healthz` returns `{"status": "ok"}` without auth. Logs go to stderr, and the server stops cleanly on Ctrl+C or SIGTERM.

### Exposing it to the internet

The [quick-start guide](docs/quickstart-ngrok.md) uses ngrok. Any HTTPS tunnel or reverse proxy works the same way: set `MCP_PUBLIC_URL` to the public base URL (its host is then accepted by the Host-header check) and enable auth. For example, [localhost.run](https://localhost.run) needs no account (`ssh -R 80:localhost:8000 nokey@localhost.run`), but its free URL changes on every reconnect, and it isn't covered by the guide.

## Connecting from Claude Code

```bash
# stdio: Claude Code starts the server itself
claude mcp add my-server -- uv run --directory /path/to/this/repo mcp-server-template

# HTTP: a server you started with --transport http
claude mcp add --transport http my-server http://127.0.0.1:8000/mcp --header "Authorization: Bearer $MCP_AUTH_TOKEN"
```

## Configuration

All settings are `MCP_*` environment variables, optionally in a `.env` file (real environment variables win). Each setting is documented in [`.env.example`](.env.example). Invalid values stop the server at startup with a message naming the variable.

| Variable | Default | Purpose |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MCP_HOST` / `MCP_PORT` / `MCP_HTTP_PATH` | `127.0.0.1` / `8000` / `/mcp` | HTTP bind address and endpoint |
| `MCP_PUBLIC_URL` | – | Public base URL behind a tunnel/proxy |
| `MCP_LOG_LEVEL` | `INFO` | Log level (stderr) |
| `MCP_AUTH_MODE` | `none` | `none`, `bearer` or `oauth` |
| `MCP_ALLOW_INSECURE` | `false` | Allow `none` on a publicly reachable server |
| `MCP_AUTH_TOKEN` | – | Bearer token (≥32 chars) |
| `MCP_OAUTH_ISSUER` / `MCP_OAUTH_JWKS_URL` / `MCP_OAUTH_RESOURCE_URL` | – | OAuth mode |
| `MCP_OAUTH_REQUIRED_SCOPES` | – | Comma-separated scopes every token needs |

## Authentication (HTTP only)

- **`none`**: only for local development. When the server is publicly reachable (it binds to a non-loopback address or has `MCP_PUBLIC_URL` set), it refuses to start unless `MCP_ALLOW_INSECURE=true`.
- **`bearer`**: every request to the MCP endpoint needs `Authorization: Bearer <MCP_AUTH_TOKEN>`. This is the recommended mode for the Voice AI web application and other single-tenant use. Generate a token with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
- **`oauth`**: the server acts as an OAuth 2.1 resource server.
  - **Accepted tokens:** JWTs signed by a key from `MCP_OAUTH_JWKS_URL`, with issuer `MCP_OAUTH_ISSUER`, an audience containing `MCP_OAUTH_RESOURCE_URL`, and every scope in `MCP_OAUTH_REQUIRED_SCOPES`.
  - **Discovery:** Protected Resource Metadata is served at `/.well-known/oauth-protected-resource` (plus the RFC 9728 path-suffixed URL).
  - **No token issuing:** the server never issues tokens; bring your own authorization server.

## Adding tools, resources and prompts

Each kind lives in its own module. Add a decorated function inside that module's `register()` and restart; nothing else needs to change.

```python
# src/mcp_server_template/tools.py
@mcp.tool()
def lookup_order(order_id: str) -> str:
    """Return the status of an order."""  # the docstring becomes the tool description
    return "shipped"
```

- **Resources** go in `resources.py`: `@mcp.resource("scheme://{param}")`.
- **Prompts** go in `prompts.py`: `@mcp.prompt()`.

Type hints become the input schema.

Tips:
- **Never `print()`** in server code. Over stdio, stdout carries the protocol, so use `logging` instead (ruff's `T20` rule flags prints).
- **Voice calls are latency-sensitive.** Keep tool calls fast (well under a second where possible), and avoid long-running work inside a tool.

## Tests and checks

```bash
uv run pytest                 # unit + integration tests (offline)
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run mypy                   # strict type checking
```

CI (`.github/workflows/ci.yml`) runs all of these on Python 3.12 and 3.13, then builds the Docker image and smoke-tests it.

## Docker

```bash
docker build -t mcp-server-template .
docker run -p 8000:8000 -e MCP_AUTH_MODE=bearer -e MCP_AUTH_TOKEN=<token> mcp-server-template
scripts/smoke-test-image.sh mcp-server-template   # optional end-to-end check
```

The image serves HTTP on `0.0.0.0:8000` as a non-root user and has a `/healthz` health check. Because it's publicly bound, it refuses to start without auth.

**Scaling note:** HTTP sessions are stateful (the SDK default), so multiple replicas need sticky sessions. If you don't need server-initiated requests, pass `stateless_http=True` to `streamable_http_app()` in `http_app.py`.

## Renaming the template

Rename `src/mcp_server_template/`, then replace `mcp_server_template` and `mcp-server-template` throughout the repository, including `pyproject.toml`, the Dockerfile and the tests. Finally run `uv sync` and the checks.
