# mcp-evals

Behavioral evaluation and description linting for [Model Context Protocol](https://modelcontextprotocol.io) (MCP) servers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yashshah9/mcp-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/yashshah9/mcp-evals/actions/workflows/ci.yml)

> **Status:** v0.4 — stdio + HTTP JSON-RPC discovery, description lint (including `name-description-mismatch`), and mock/OpenAI-compatible tool-selection evals.

## 60-second try

```bash
docker compose run --rm run-example   # mock eval, no API key
docker compose run --rm lint-example  # live stdio lint
docker compose run --rm test          # pytest
```

## Why this vs alternatives

| Approach | Strength | Gap |
|----------|----------|-----|
| **mcp-evals** | Lint + YAML evals + mock CI runner | Not a full agent harness |
| MCP Inspector | Interactive debugging | No CI lint/eval suite |
| Protocol conformance tests | JSON-RPC correctness | Do not test tool selection |
| Hand-written LLM mocks | Full control | Drift from real descriptions |

## Problem

Protocol conformance tests verify JSON-RPC correctness. They do **not** verify whether an LLM agent selects the right tool, passes sensible arguments, or completes the task. Tool descriptions are now load-bearing API design, and there is no standard way to test them.

**mcp-evals** fills the behavioral layer: lint tool descriptions, define eval cases in YAML, and (next) measure tool-selection accuracy in CI.

## Key features (v0.4)

- **Description linter** — missing descriptions, undocumented required params, overlapping tools, ambiguous verbs, `name-description-mismatch`
- **Live discover** — handshake a stdio or HTTP JSON-RPC MCP server (or load a catalog fixture)
- **Eval runner** — `mcp-evals run` with `--model mock` (CI), `--live SERVER.yaml`, or an OpenAI-compatible endpoint
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
pip install mcp-tool-evals
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

# Lint a live stdio server (this example passes)
docker compose run --rm lint-example

# Discover tools from the example calc server
docker compose run --rm discover-example

# Mock eval run (no API key)
docker compose run --rm run-example
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
# or discover tools from a live server that matches the suite:
# mcp-evals run suite.yaml --live server.yaml --model mock
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
- [x] HTTP JSON-RPC MCP transport
- [x] `name-description-mismatch` linter rule
- [ ] Streamable HTTP/SSE MCP transport
- [ ] GitHub Action PR comments and accuracy deltas

## Known limitations (v0.4)

- Streamable HTTP/SSE MCP is not implemented — HTTP is JSON-RPC POST only
- Mock selector does not fill tool arguments (accuracy is tool-name only)
- Live Ollama/OpenAI evals need a reachable `--base-url`; CI uses `--model mock`
- `examples/tools.yaml` is intentionally dirty so `mcp-evals lint` can show findings

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
