# Contributing to mcp-evals

Thank you for your interest in contributing.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install  # optional
```

## Running tests

Prefer Docker Compose so the environment matches CI:

```bash
docker compose run --rm test
```

Locally:

```bash
pytest tests/ -v
ruff check src tests
mypy src
```

Other useful compose services: `dev`, `lint-example`, `discover-example`, `run-example`.

## Project layout

| Path | Purpose |
|------|---------|
| `src/mcp_evals/cli.py` | CLI entry point |
| `src/mcp_evals/linter/` | Static description analysis |
| `src/mcp_evals/runner/` | Eval execution |
| `src/mcp_evals/models/` | Pydantic schemas |
| `examples/` | Sample catalogs and eval suites |

## Pull requests

- Keep changes focused and tested
- Update README/CHANGELOG for user-facing changes
- Follow existing code style (ruff + mypy strict)
- Prefer small PRs with a clear test plan in the description

## Commit style

- Imperative subject line; mention the user-facing why when relevant
- Do not add AI co-author trailers (e.g. Co-authored-by: Cursor) to commits.
