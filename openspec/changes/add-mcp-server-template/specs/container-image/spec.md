## Purpose

Defines the container image used to deploy the server over Streamable HTTP, so derived servers can be shipped to any container platform with secure defaults.

## ADDED Requirements

### Requirement: Buildable image serving HTTP
The repository SHALL contain a Dockerfile that builds an image from a clean checkout with no build arguments. Running the image SHALL start the server over Streamable HTTP, bound to `0.0.0.0` on port `8000`, with the port declared via `EXPOSE`.

#### Scenario: Build and run
- **WHEN** the image is built and run with `-p 8000:8000` and `MCP_AUTH_MODE=bearer` plus `MCP_AUTH_TOKEN` set
- **THEN** `GET http://localhost:8000/healthz` returns HTTP 200 and an authenticated MCP `initialize` request succeeds

#### Scenario: Run without auth configuration
- **WHEN** the image is run with no auth settings
- **THEN** the container exits with a non-zero status and an error explaining that authentication must be configured (per the http-auth insecure-bind rule)

### Requirement: Secure, minimal runtime image
The runtime image SHALL run as a non-root user, SHALL NOT contain build tooling, tests, `.git`, or `.env` files, and SHALL pin its base image to a specific Python minor version.

#### Scenario: Runs as non-root
- **WHEN** the container's effective user is inspected
- **THEN** it is not UID 0

#### Scenario: Secrets not baked in
- **WHEN** a `.env` file exists in the build context and the image is built
- **THEN** the image does not contain that `.env` file

### Requirement: Container health check
The image SHALL declare a `HEALTHCHECK` that queries `/healthz`.

#### Scenario: Healthy container
- **WHEN** the container has started successfully
- **THEN** the container runtime reports it as healthy
