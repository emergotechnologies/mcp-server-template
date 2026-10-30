## Purpose

Gives developers one-command setup, testing and quality checks, and enforces them in CI, so every server built from the template stays correct and consistently formatted.

## ADDED Requirements

### Requirement: Reproducible local setup
The project SHALL declare all runtime and development dependencies with a committed lockfile, so that a single documented command installs an environment identical to CI's.

#### Scenario: Fresh clone setup
- **WHEN** a developer runs the documented setup command on a fresh clone with the required Python and package manager installed
- **THEN** all dependencies install from the lockfile without manual steps

### Requirement: Automated tests
The project SHALL include a test suite runnable with one documented command that covers: each example primitive via an in-process MCP client; configuration loading and validation errors; each HTTP auth mode (accepted, rejected, and unauthenticated endpoints) without network access to real identity providers; and the stdio transport end-to-end by launching the server as a subprocess.

#### Scenario: Tests pass on a clean checkout
- **WHEN** the test command is run after setup
- **THEN** all tests pass without network access or external services

#### Scenario: Regression is caught
- **WHEN** the `add` tool is changed to return an incorrect result
- **THEN** the test command exits non-zero

### Requirement: Lint, format and type checks
The project SHALL provide documented commands for linting, format checking and static type checking over source and tests, each exiting non-zero on violations.

#### Scenario: Formatting violation
- **WHEN** a source file is not formatted per the project's formatter configuration
- **THEN** the format-check command exits non-zero

#### Scenario: Type error
- **WHEN** a source file contains a type error
- **THEN** the type-check command exits non-zero

### Requirement: Continuous integration
The repository SHALL include a GitHub Actions workflow that runs on pushes to `main` and on pull requests, and executes lint, format check, type check, tests, and a Docker image build. The workflow SHALL fail if any step fails.

#### Scenario: Pull request with failing test
- **WHEN** a pull request introduces a failing test
- **THEN** the CI workflow reports failure on that pull request

#### Scenario: Clean pull request
- **WHEN** a pull request passes all checks and the image builds
- **THEN** the CI workflow reports success

### Requirement: Local + ngrok quick-start guide
The repository SHALL include a quick-start guide at `docs/quickstart-ngrok.md`, linked from the top of the README, for hackathon participants. It SHALL be short (fits on roughly one printed page, no more than 8 numbered steps) and precise (every step is a copy-pasteable command or an exact value to enter). It SHALL cover, in order:
1. Prerequisites: Python, `uv`, `git`, and a free ngrok account (with a note that ngrok requires users to be 18+, and that each participant uses their own account).
2. Install ngrok and register the authtoken (`ngrok config add-authtoken <token>`).
3. Clone and install (`uv sync`).
4. Start ngrok in a second terminal (`ngrok http 8000`; on the free plan this uses the account's fixed dev domain) and copy the `Forwarding` URL.
5. Create `.env` (settings documented in `.env.example`) with `MCP_TRANSPORT=http`, `MCP_AUTH_MODE=bearer`, a generated `MCP_AUTH_TOKEN` (with the command to generate it), and `MCP_PUBLIC_URL` set to the dev domain.
6. Start the server.
7. Verify: `curl` the public `/healthz`, plus an authenticated MCP `initialize` request expected to succeed and an unauthenticated one expected to return 401.
8. Configure the MCP server in the Voice AI web application: server URL `https://<dev-domain>/mcp`, header `Authorization: Bearer <token>`.

It SHALL end with a short troubleshooting table covering at least: 401 Unauthorized (token mismatch); host rejected (`MCP_PUBLIC_URL` does not match the ngrok domain); ngrok browser warning page (affects browsers only; `ngrok-skip-browser-warning` header); `ERR_NGROK_...` endpoint already online (stop the other ngrok session); and free-plan limits reached (about 20k requests / 1 GB per month per account). It SHALL also include a pointer to where new tools are added.

#### Scenario: Participant connects the Voice AI web application
- **WHEN** a participant with Python, `uv` and a free ngrok account follows only `docs/quickstart-ngrok.md` on a fresh clone
- **THEN** all verification commands in step 7 produce the documented results, and the Voice AI web application can list and call the example `add` tool through the ngrok URL

#### Scenario: Guide stays short
- **WHEN** the guide is reviewed
- **THEN** it has at most 8 numbered steps, and every command in it was run successfully against the implemented template

### Requirement: Documentation
The repository SHALL include a README covering: purpose; prerequisites; setup; running over stdio and HTTP; connecting the server to Claude Code; every configuration variable (or a pointer to `.env.example`); each auth mode; adding tools, resources and prompts; running tests and checks; and building and running the container.

#### Scenario: New developer onboarding
- **WHEN** a developer follows only the README from a fresh clone
- **THEN** they can run the tests, start the server over stdio and HTTP, and connect it to Claude Code
