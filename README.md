# mcp-evals

Behavioral evaluation and description linting for [Model Context Protocol](https://modelcontextprotocol.io) (MCP) servers.

> **Status:** v0.3 — stdio + HTTP JSON-RPC discovery, description lint, and mock/OpenAI-compatible tool-selection evals.

## Problem

Protocol conformance tests verify JSON-RPC correctness. They do **not** verify whether an LLM agent selects the right tool, passes sensible arguments, or completes the task. Tool descriptions are now load-bearing API design, and there is no standard way to test them.

**mcp-evals** fills the behavioral layer: lint tool descriptions, define eval cases in YAML, and (next) measure tool-selection accuracy in CI.

## Key features (v0.2)

- **Description linter** — missing descriptions, undocumented required params, overlapping tools, ambiguous verbs
- **Live discover** — handshake a stdio MCP server (or load a catalog fixture)
- **Eval runner** — `mcp-evals run` with `--model mock` (CI) or an OpenAI-compatible endpoint
- **CLI + Docker + GitHub Action** — lint and optional eval in CI without a cloud key (mock selector)

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  CLI        │────▶│  Linter / Runner │────▶│  Models (Pydantic)│
│  mcp-evals  │     │  spec_loader     │     │  EvalSuite, etc.  │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                    (next) MCP client + LLM
```

| Component | Technology | Why |
|-----------|------------|-----|
| Language | Python 3.11+ | MCP SDK ecosystem, pytest integration |
| CLI | Click | Mature, composable commands |
| Schemas | Pydantic v2 | Strict validation, good errors |
| Logging | structlog | Structured, JSON-capable |
| Config | pydantic-settings | Env-based, typed |
| Tests | pytest + ruff + mypy | Standard Python OSS stack |

## Installation

```bash
pip install mcp-evals
# or from source:
pip install -e ".[dev]"
```

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mcp-evals health
mcp-evals lint examples/tools.yaml
mcp-evals discover examples/server.yaml
mcp-evals lint --live examples/server.yaml
mcp-evals validate-spec examples/eval-suite.yaml
mcp-evals run examples/eval-suite.yaml --catalog examples/tools.yaml --model mock
pytest tests/ -v
```

## Docker

```bash
# Health check
docker compose run --rm dev

# Run tests
docker compose run --rm test

# Lint example catalog
docker compose run --rm lint-example
```

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_EVALS_LOG_LEVEL` | `INFO` | Log level |
| `MCP_EVALS_LOG_JSON` | `false` | JSON log output |
| `MCP_EVALS_DEFAULT_MODEL` | `gpt-4o-mini` | Model for eval runs (future) |
| `MCP_EVALS_PASS_THRESHOLD` | `0.8` | Minimum selection accuracy |

## Usage

### Lint tool descriptions

```bash
mcp-evals lint examples/tools.yaml
mcp-evals lint --live examples/server.yaml
mcp-evals discover examples/server.yaml
mcp-evals lint examples/tools.yaml --format json
mcp-evals lint examples/tools.yaml --fail-on-warning
```

### Run behavioral evals

```bash
mcp-evals run examples/eval-suite.yaml --catalog examples/tools.yaml --model mock
mcp-evals run examples/eval-suite.yaml --catalog examples/tools.yaml \
  --model llama3.2 --base-url http://localhost:11434/v1 --pass-threshold 0.8
```

### Validate eval suite

```bash
mcp-evals validate-spec examples/eval-suite.yaml
```

### Health check

```bash
mcp-evals health
```

## Example eval suite

See `examples/eval-suite.yaml`:

```yaml
name: document-server-behavior
cases:
  - id: search-by-keyword
    request: Find documents about quarterly revenue
    expected_tool:
      name: search_documents
      arguments:
        query: quarterly revenue
```

## Running tests

```bash
pytest tests/ -v
ruff check src tests
mypy src
```

## Development workflow

1. Add linter rules in `src/mcp_evals/linter/`
2. Add runner logic in `src/mcp_evals/runner/`
3. Add tests in `tests/`
4. Update examples in `examples/`

## Roadmap

- [x] MCP client: stdio discover + lint --live
- [x] LLM eval runner (mock + OpenAI-compatible)
- [ ] HTTP/Streamable MCP transport
- [ ] GitHub Action PR comments and accuracy deltas

## Known limitations (v0.2)

- HTTP MCP transport is not implemented — use stdio or a catalog fixture
- Mock selector does not fill tool arguments (accuracy is tool-name only)
- Live Ollama/OpenAI evals need a reachable `--base-url`; CI uses `--model mock`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
