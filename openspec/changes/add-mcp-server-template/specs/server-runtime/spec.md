## Purpose

Defines how the MCP server starts, which transport it serves, how it is configured, and how operators observe it, so every server derived from the template behaves the same way at runtime.

## ADDED Requirements

### Requirement: Single entry point with transport selection
The server SHALL be started through a single command-line entry point that serves the MCP protocol over either the stdio transport or the Streamable HTTP transport. The transport SHALL be selectable by a `--transport` option (`stdio` or `http`) and by the `MCP_TRANSPORT` environment variable, with the command-line option taking precedence. When neither is given, the server SHALL use stdio.

#### Scenario: Default transport is stdio
- **WHEN** the entry point is run with no transport option and `MCP_TRANSPORT` unset
- **THEN** the server communicates over stdin/stdout and responds to an MCP `initialize` request

#### Scenario: HTTP selected by environment variable
- **WHEN** the entry point is run with `MCP_TRANSPORT=http`
- **THEN** the server listens for Streamable HTTP requests instead of reading stdin

#### Scenario: Command-line option overrides environment
- **WHEN** the entry point is run with `MCP_TRANSPORT=http` and `--transport stdio`
- **THEN** the server uses the stdio transport

#### Scenario: Invalid transport value
- **WHEN** the transport is set to a value other than `stdio` or `http`
- **THEN** the process exits with a non-zero status and an error message naming the allowed values, without starting a server

### Requirement: Environment-based configuration
All runtime settings SHALL be read from environment variables prefixed with `MCP_`, optionally loaded from a `.env` file in the working directory, with real environment variables taking precedence over `.env`. Settings SHALL be validated at startup, and every setting SHALL be documented in a committed `.env.example` file.

#### Scenario: Defaults apply when nothing is configured
- **WHEN** the server starts with no `MCP_` variables and no `.env` file
- **THEN** it starts successfully using the documented defaults (stdio transport; for HTTP, host `127.0.0.1`, port `8000`, path `/mcp`)

#### Scenario: Invalid setting fails fast
- **WHEN** a setting has an invalid value (for example `MCP_PORT=not-a-number`)
- **THEN** the process exits with a non-zero status and an error naming the offending variable before serving any request

### Requirement: Streamable HTTP endpoint
When running over HTTP, the server SHALL bind to the configured host (`MCP_HOST`) and port (`MCP_PORT`) and serve the MCP Streamable HTTP protocol at the configured path (`MCP_HTTP_PATH`).

#### Scenario: Client connects over HTTP
- **WHEN** an MCP client sends an `initialize` request to `http://<host>:<port><path>` with valid credentials (if auth is enabled)
- **THEN** the server returns a successful initialize result including its name and version

### Requirement: Public URL and allowed hosts
The server SHALL accept an optional `MCP_PUBLIC_URL` setting holding the externally reachable base URL (for example an ngrok domain such as `https://example.ngrok-free.app`). Over HTTP, the server SHALL validate the `Host` header of MCP requests (DNS-rebinding protection) and SHALL accept only local hosts (`localhost`, `127.0.0.1`, with the configured port) plus the host of `MCP_PUBLIC_URL` when set. On startup over HTTP, the server SHALL log the full public MCP endpoint (`MCP_PUBLIC_URL` + `MCP_HTTP_PATH`) when a public URL is configured.

#### Scenario: Request through a tunnel is accepted
- **WHEN** `MCP_PUBLIC_URL=https://example.ngrok-free.app` and an authenticated MCP request arrives with `Host: example.ngrok-free.app`
- **THEN** the request is processed normally

#### Scenario: Unknown host is rejected
- **WHEN** an MCP request arrives with a `Host` header that is neither local nor the host of `MCP_PUBLIC_URL`
- **THEN** the server rejects it with an HTTP 4xx error without processing the MCP request

#### Scenario: Invalid public URL
- **WHEN** `MCP_PUBLIC_URL` is not an absolute `http` or `https` URL
- **THEN** the process exits with a non-zero status naming `MCP_PUBLIC_URL`

#### Scenario: Public endpoint is logged
- **WHEN** the server starts over HTTP with `MCP_PUBLIC_URL=https://example.ngrok-free.app` and the default path
- **THEN** the startup log contains `https://example.ngrok-free.app/mcp`

### Requirement: Health endpoint
When running over HTTP, the server SHALL expose `GET /healthz` that returns HTTP 200 with a JSON body containing `"status": "ok"`. This endpoint SHALL NOT require authentication.

#### Scenario: Health check succeeds
- **WHEN** a client sends `GET /healthz` without credentials
- **THEN** the response is HTTP 200 with body containing `"status": "ok"`

### Requirement: Logging that does not corrupt stdio
The server SHALL write all logs to stderr, never stdout, at the level set by `MCP_LOG_LEVEL` (default `INFO`). Logs SHALL NOT contain secrets such as bearer tokens.

#### Scenario: Logs under stdio transport
- **WHEN** the server runs over stdio and emits log messages
- **THEN** stdout contains only valid MCP JSON-RPC messages and the log output appears on stderr

#### Scenario: Log level respected
- **WHEN** `MCP_LOG_LEVEL=WARNING`
- **THEN** INFO and DEBUG messages are not emitted

### Requirement: Graceful shutdown
The server SHALL shut down cleanly on SIGINT or SIGTERM, and on end-of-input when using stdio, exiting with status 0.

#### Scenario: SIGTERM during HTTP serving
- **WHEN** the HTTP server receives SIGTERM
- **THEN** it stops accepting new connections and the process exits with status 0
