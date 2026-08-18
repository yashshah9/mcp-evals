"""Load eval specs and tool catalogs from YAML/JSON files."""

from pathlib import Path

import yaml

from mcp_evals.errors import SpecValidationError
from mcp_evals.models.spec import EvalSuite, ToolCatalog


def load_eval_suite(path: Path) -> EvalSuite:
    """Load and validate an eval suite from YAML."""
    if not path.exists():
        raise SpecValidationError(f"Eval suite not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SpecValidationError("Eval suite must be a YAML mapping.")
    try:
        return EvalSuite.model_validate(raw)
    except Exception as exc:
        raise SpecValidationError(f"Invalid eval suite: {exc}") from exc


def load_tool_catalog(path: Path) -> ToolCatalog:
    """Load a tool catalog fixture for linting without a live MCP server."""
    if not path.exists():
        raise SpecValidationError(f"Tool catalog not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SpecValidationError("Tool catalog must be a YAML mapping.")
    try:
        return ToolCatalog.model_validate(raw)
    except Exception as exc:
        raise SpecValidationError(f"Invalid tool catalog: {exc}") from exc
