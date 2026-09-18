# Changelog

## [0.8.1] - 2026-09-19

- Args gate case pass; stdio byte framing; HTTP session + initialized


All notable changes to this project will be documented in this file.

## [0.8.0] - 2026-09-18

### Added
- Mock `KeywordSelector` now **infers tool arguments** from the request using each tool’s JSON Schema `properties` / `required`
- Argument validity is scored in CI mock runs when `expected_tool.arguments` is set (no longer tool-name-only)

### Changed
- Eval case messages include `args=ok` or the actual inferred args when expectations are present

## [0.7.0] - 2026-09-14

### Added
- Streamable HTTP / SSE MCP discovery (`transport: sse` or `streamable-http`)
- `mcp_evals.mcp_client.sse.discover_sse` — POST JSON-RPC with `Accept: application/json, text/event-stream`, parse SSE `data:` events, echo `Mcp-Session-Id`
- Example server config `examples/sse-server.yaml`
- Unit tests with mocked httpx SSE framing (`tests/test_sse_client.py`)

## [0.6.0] - 2026-09-14

### Added
- GitHub Action PR comment (or job summary) with selection accuracy and per-case table
- Action input `comment` (default `true`) to toggle PR comments

## [0.5.0] - 2026-09-14

### Added
- `missing-examples` linter rule — info when inputSchema has properties but no schema- or property-level examples

## [0.4.0] - 2026-09-14

### Added
- `name-description-mismatch` linter rule — warns when distinctive tool-name tokens never appear in the description

## [0.3.0] - 2026-08-19

### Added
- HTTP JSON-RPC MCP discovery (`transport: http` + `mcp_evals.mcp_client.http`)
- Example HTTP calculator server in `examples/http_server.py`

## [0.2.0] - 2026-08-19

### Added
- `mcp-evals discover` for stdio MCP servers and catalog fixtures
- `mcp-evals lint --live` against a server config
- Behavioral `mcp-evals run` with mock keyword selector or OpenAI-compatible models
- `--samples` and `--pass-threshold` for CI
- Extra linter rules: `required-params-undocumented`, `ambiguous-verbs`
- Example stdio calculator server and GitHub Action (`action.yml`)

### Notes
- Streamable HTTP/SSE shipped in 0.7.0

## [0.1.0] - 2026-08-18

### Added
- Initial project foundation
- `mcp-evals lint` — static tool description linter
- `mcp-evals validate-spec` — eval suite structure validation (dry-run)
- `mcp-evals health` — installation check
- Example tool catalog and eval suite fixtures
- Docker development and test environment
