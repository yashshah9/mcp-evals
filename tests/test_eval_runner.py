"""Tests for discovery and behavioral eval runner."""

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from mcp_evals.errors import DiscoveryError
from mcp_evals.mcp_client.discover import discover_tools, load_server_config
from mcp_evals.mcp_client.http import discover_http
from mcp_evals.models.server import ServerConfig
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


def test_discover_http_calc_server() -> None:
    sys.path.insert(0, str(EXAMPLES))
    from http_server import Handler  # type: ignore[import-not-found]

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        url = f"http://{host}:{port}"
        catalog = discover_http(url, timeout=3)
        assert {t.name for t in catalog.tools} == {"add", "echo"}
        config = ServerConfig(name="calc-http", transport="http", url=url)
        via_config = discover_tools(config)
        assert len(via_config.tools) == 2
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_discover_http_bad_url() -> None:
    with pytest.raises(DiscoveryError):
        discover_http("http://127.0.0.1:1", timeout=0.3)
