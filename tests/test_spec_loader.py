"""Tests for spec loading and validation."""

from pathlib import Path

import pytest

from mcp_evals.errors import SpecValidationError
from mcp_evals.runner.eval_runner import validate_suite_structure
from mcp_evals.spec_loader import load_eval_suite, load_tool_catalog


EXAMPLES = Path(__file__).parent.parent / "examples"


def test_load_tool_catalog_example() -> None:
    catalog = load_tool_catalog(EXAMPLES / "tools.yaml")
    assert len(catalog.tools) == 3


def test_load_eval_suite_example() -> None:
    suite = load_eval_suite(EXAMPLES / "eval-suite.yaml")
    assert suite.name == "document-server-behavior"
    assert len(suite.cases) == 2


def test_validate_suite_structure_passes() -> None:
    suite = load_eval_suite(EXAMPLES / "eval-suite.yaml")
    report = validate_suite_structure(suite)
    assert report.passed


def test_load_missing_spec_raises() -> None:
    with pytest.raises(SpecValidationError):
        load_eval_suite(Path("/nonexistent/suite.yaml"))
