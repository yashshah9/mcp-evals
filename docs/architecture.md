# Architecture

## Overview

mcp-evals is a Python CLI library with three layers:

1. **CLI** (`cli.py`) — user-facing commands
2. **Core** (`linter/`, `runner/`, `spec_loader.py`) — business logic
3. **Models** (`models/`) — Pydantic schemas for eval suites and tool catalogs

## Data flow

```
YAML fixtures → spec_loader → linter / runner → Rich/JSON report
```

Future: MCP client discovery → LLM eval loop → GitHub Action reporter.

## Extension points

| Add feature | Location |
|-------------|----------|
| New linter rule | `src/mcp_evals/linter/` |
| LLM provider | `src/mcp_evals/runner/` (planned) |
| MCP transport | `src/mcp_evals/mcp_client/` (planned) |
