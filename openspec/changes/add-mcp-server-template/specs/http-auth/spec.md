## Purpose

Protects the Streamable HTTP transport so a deployed server only serves authorized clients, supporting a simple shared-token mode and an OAuth 2.1 resource-server mode compatible with the MCP authorization specification.

## ADDED Requirements

### Requirement: Selectable auth mode
The HTTP transport SHALL support three authentication modes selected by `MCP_AUTH_MODE`: `none`, `bearer` and `oauth`. The default SHALL be `none`. The server SHALL treat itself as publicly exposed when it binds to a non-loopback address **or** `MCP_PUBLIC_URL` is set (a tunnel such as ngrok forwards public traffic to a loopback address). When it is publicly exposed with auth mode `none`, it SHALL refuse to start unless `MCP_ALLOW_INSECURE=true` is set. Auth settings SHALL have no effect on the stdio transport.

#### Scenario: Unauthenticated local development
- **WHEN** the server runs over HTTP on `127.0.0.1` with `MCP_AUTH_MODE` unset
- **THEN** MCP requests without an `Authorization` header succeed

#### Scenario: Refuse insecure public bind
- **WHEN** the server is started over HTTP with `MCP_HOST=0.0.0.0` and auth mode `none` and `MCP_ALLOW_INSECURE` not set
- **THEN** the process exits with a non-zero status and an error explaining how to enable auth

#### Scenario: Refuse unauthenticated tunnel
- **WHEN** the server is started over HTTP on `127.0.0.1` with `MCP_PUBLIC_URL` set, auth mode `none`, and `MCP_ALLOW_INSECURE` not set
- **THEN** the process exits with a non-zero status and an error explaining that a publicly reachable server needs `MCP_AUTH_MODE=bearer` and `MCP_AUTH_TOKEN`

#### Scenario: Explicit insecure override
- **WHEN** the same configuration sets `MCP_ALLOW_INSECURE=true`
- **THEN** the server starts and logs a warning that authentication is disabled

#### Scenario: Missing settings for selected mode
- **WHEN** `MCP_AUTH_MODE=bearer` without `MCP_AUTH_TOKEN`, or `MCP_AUTH_MODE=oauth` without issuer, JWKS URL, or resource URL
- **THEN** the process exits with a non-zero status naming the missing setting

### Requirement: Static bearer token mode
In `bearer` mode the server SHALL require every MCP request to carry `Authorization: Bearer <token>` where the token equals `MCP_AUTH_TOKEN`. Comparison SHALL be constant-time. The server SHALL refuse to start if `MCP_AUTH_TOKEN` is shorter than 32 characters, so hackathon participants cannot expose a guessable token. Bearer mode is the recommended mode for connecting the Voice AI web application.

#### Scenario: Token too short
- **WHEN** `MCP_AUTH_MODE=bearer` and `MCP_AUTH_TOKEN=secret`
- **THEN** the process exits with a non-zero status, naming `MCP_AUTH_TOKEN` and showing a command that generates a suitable token

#### Scenario: Valid token
- **WHEN** a request carries `Authorization: Bearer <configured token>`
- **THEN** the request is processed normally

#### Scenario: Missing or wrong token
- **WHEN** a request has no `Authorization` header or a different token
- **THEN** the server responds HTTP 401 with a `WWW-Authenticate: Bearer` header and does not process the MCP request

### Requirement: OAuth 2.1 resource server mode
In `oauth` mode the server SHALL act as an OAuth 2.1 resource server: it SHALL accept only JWT access tokens that are signed by a key from the configured JWKS URL (`MCP_OAUTH_JWKS_URL`), issued by the configured issuer (`MCP_OAUTH_ISSUER`), whose audience includes the server's canonical resource URL (`MCP_OAUTH_RESOURCE_URL`), and that are not expired. When `MCP_OAUTH_REQUIRED_SCOPES` is set, the token SHALL contain all listed scopes. The server SHALL NOT issue tokens itself.

#### Scenario: Valid access token
- **WHEN** a request carries a correctly signed, unexpired JWT with the configured issuer, audience and required scopes
- **THEN** the request is processed normally

#### Scenario: Invalid token
- **WHEN** a request carries a token that is expired, has the wrong issuer or audience, or has an invalid signature
- **THEN** the server responds HTTP 401 with `WWW-Authenticate: Bearer error="invalid_token"` and a `resource_metadata` parameter pointing to the Protected Resource Metadata URL

#### Scenario: Insufficient scope
- **WHEN** a valid token lacks a required scope
- **THEN** the server responds HTTP 403 with `WWW-Authenticate: Bearer error="insufficient_scope"`

#### Scenario: No token
- **WHEN** a request has no `Authorization` header
- **THEN** the server responds HTTP 401 with a `WWW-Authenticate` header including the `resource_metadata` URL, so clients can discover the authorization server

### Requirement: Protected Resource Metadata
In `oauth` mode the server SHALL publish OAuth 2.0 Protected Resource Metadata (RFC 9728) at `/.well-known/oauth-protected-resource` without requiring authentication. The document SHALL include `resource` (the canonical resource URL) and `authorization_servers` (containing the configured issuer), and SHALL include `scopes_supported` when required scopes are configured.

#### Scenario: Metadata is discoverable
- **WHEN** a client sends `GET /.well-known/oauth-protected-resource` without credentials
- **THEN** the response is HTTP 200 JSON containing the configured resource URL and issuer

### Requirement: Unauthenticated operational endpoints
In every auth mode, `GET /healthz` and (in `oauth` mode) the Protected Resource Metadata endpoint SHALL remain reachable without credentials. All MCP protocol requests SHALL require authentication whenever the mode is not `none`.

#### Scenario: Health check with auth enabled
- **WHEN** auth mode is `bearer` or `oauth` and a client sends `GET /healthz` with no credentials
- **THEN** the response is HTTP 200
