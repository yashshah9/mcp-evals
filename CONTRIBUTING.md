# Contributing to mcp-evals

Thank you for your interest in contributing.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install  # optional
```

## Running tests

```bash
pytest tests/ -v
ruff check src tests
mypy src
```

## Docker

```bash
docker compose -f compose.yaml run --rm test
```

## Project layout

| Path | Purpose |
|------|---------|
| `src/mcp_evals/cli.py` | CLI entry point |
| `src/mcp_evals/linter/` | Static description analysis |
| `src/mcp_evals/runner/` | Eval execution (LLM integration next) |
| `src/mcp_evals/models/` | Pydantic schemas |
| `examples/` | Sample catalogs and eval suites |

## Pull requests

- Keep changes focused and tested
- Update README/CHANGELOG for user-facing changes
- Follow existing code style (ruff + mypy strict)
