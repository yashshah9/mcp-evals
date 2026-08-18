"""Tests for discovery and behavioral eval runner."""

from pathlib import Path

from mcp_evals.mcp_client.discover import discover_tools, load_server_config
from mcp_evals.models.spec import EvalCase, EvalSuite, ToolCatalog, ToolDefinition, ToolExpectation
from mcp_evals.runner.llm_runner import KeywordSelector, run_eval_suite

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_discover_catalog_transport() -> None:
    config = load_server_config(EXAMPLES / "catalog-server.yaml")
    catalog = discover_tools(config, base_dir=EXAMPLES)
    assert len(catalog.tools) == 3


def test_discover_stdio_calc_server() -> None:
    config = load_server_config(EXAMPLES / "server.yaml")
    catalog = discover_tools(config, base_dir=EXAMPLES)
    names = {t.name for t in catalog.tools}
    assert names == {"add", "echo"}


def test_keyword_selector_picks_expected_tool() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(name="search_documents", description="Search documents by keyword."),
            ToolDefinition(name="fetch_document", description="Retrieve one document by id."),
        ]
    )
    suite = EvalSuite(
        name="demo",
        cases=[
            EvalCase(
                id="search",
                request="Search documents about revenue",
                expected_tool=ToolExpectation(name="search_documents"),
            )
        ],
    )
    report, metrics = run_eval_suite(suite, catalog, KeywordSelector(), samples=1)
    assert report.passed
    assert metrics.selection_accuracy == 1.0
