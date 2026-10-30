## Purpose

Provides one working example of each MCP primitive (tool, resource, prompt) and a consistent place to add new ones, so developers copy a tested pattern instead of starting from the SDK docs.

## ADDED Requirements

### Requirement: Example tool
The server SHALL expose a tool named `add` that takes two numeric arguments `a` and `b` and returns their sum. The tool SHALL publish an input schema declaring both arguments as required numbers, and a human-readable description.

#### Scenario: Tool is listed
- **WHEN** a client calls `tools/list`
- **THEN** the result includes a tool named `add` with a description and an input schema requiring numeric `a` and `b`

#### Scenario: Tool returns sum
- **WHEN** a client calls `add` with `a = 2` and `b = 3`
- **THEN** the result is not an error and its content contains `5`

#### Scenario: Invalid arguments
- **WHEN** a client calls `add` with `a = "two"`
- **THEN** the server returns an error result describing the invalid argument and does not crash

### Requirement: Example static resource
The server SHALL expose a static resource at URI `info://server` that returns JSON describing the server, including at least its name and version.

#### Scenario: Static resource is listed and readable
- **WHEN** a client calls `resources/list` and then `resources/read` for `info://server`
- **THEN** the list includes `info://server` and the read returns JSON content containing the server name and version

### Requirement: Example resource template
The server SHALL expose a resource template `greeting://{name}` that returns a plain-text greeting addressing the supplied name.

#### Scenario: Template is listed
- **WHEN** a client calls `resources/templates/list`
- **THEN** the result includes the URI template `greeting://{name}`

#### Scenario: Template is read
- **WHEN** a client reads `greeting://Ada`
- **THEN** the returned text contains `Ada`

### Requirement: Example prompt
The server SHALL expose a prompt named `code_review` that takes a required `code` argument and returns at least one user message asking for a review of that code.

#### Scenario: Prompt is listed
- **WHEN** a client calls `prompts/list`
- **THEN** the result includes `code_review` with a required argument named `code`

#### Scenario: Prompt is rendered
- **WHEN** a client calls `prompts/get` for `code_review` with `code = "print(1)"`
- **THEN** the result contains a user message whose text includes `print(1)`

#### Scenario: Missing required argument
- **WHEN** a client calls `prompts/get` for `code_review` without `code`
- **THEN** the server returns an error

### Requirement: Primitive registration convention
Tools, resources and prompts SHALL each live in a dedicated module, and adding a new primitive SHALL require changes only within that module (no edits to transport, configuration or auth code). The README SHALL document how to add each kind of primitive.

#### Scenario: Adding a tool
- **WHEN** a developer adds a new decorated function to the tools module following the documented pattern
- **THEN** the new tool appears in `tools/list` on next start without changes elsewhere

### Requirement: Primitives are transport- and auth-independent
Every example primitive SHALL behave identically over stdio and Streamable HTTP.

#### Scenario: Same result over both transports
- **WHEN** the same `add` call is made over stdio and over authenticated HTTP
- **THEN** both return the same result
