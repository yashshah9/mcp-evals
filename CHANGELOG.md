# Changelog

All notable changes to this project will be documented in this file.

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
- HTTP/Streamable MCP transport is not implemented yet

## [0.1.0] - 2026-08-18

### Added
- Initial project foundation
- `mcp-evals lint` — static tool description linter
- `mcp-evals validate-spec` — eval suite structure validation (dry-run)
- `mcp-evals health` — installation check
- Example tool catalog and eval suite fixtures
- Docker development and test environment
