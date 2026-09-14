"""Robustness scenarios for mcp-evals v0.5 features and existing behavior."""

from pathlib import Path

import pytest
import yaml

from mcp_evals.errors import DiscoveryError, EvalRunError, SpecValidationError
from mcp_evals.linter.descriptions import lint_tool_descriptions
from mcp_evals.mcp_client.discover import discover_tools, load_server_config
from mcp_evals.models.server import ServerConfig
from mcp_evals.models.spec import (
    EvalCase,
    EvalSuite,
    ToolCatalog,
    ToolDefinition,
    ToolExpectation,
)
from mcp_evals.runner.eval_runner import validate_suite_structure
from mcp_evals.runner.llm_runner import KeywordSelector, run_eval_suite
from mcp_evals.spec_loader import load_eval_suite, load_tool_catalog

# --- missing-examples ---


def test_missing_examples_fires_without_any_examples() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a new GitHub issue in the configured repository.",
                parameters={
                    "properties": {
                        "title": {"type": "string", "description": "Issue title"},
                    }
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_with_property_level_examples() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a new GitHub issue in the configured repository.",
                parameters={
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Issue title",
                            "examples": ["Bug in login"],
                        },
                    }
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_with_property_level_singular_example() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a new GitHub issue in the configured repository.",
                parameters={
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Issue title",
                            "example": "Bug in login",
                        },
                    }
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_with_schema_level_examples() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a new GitHub issue in the configured repository.",
                parameters={
                    "examples": [{"title": "Bug in login"}],
                    "properties": {
                        "title": {"type": "string", "description": "Issue title"},
                    },
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_with_schema_level_singular_example() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a new GitHub issue in the configured repository.",
                parameters={
                    "example": {"title": "Bug in login"},
                    "properties": {
                        "title": {"type": "string", "description": "Issue title"},
                    },
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_when_properties_empty() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="ping",
                description="Health-check ping that returns ok status.",
                parameters={"type": "object", "properties": {}},
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


def test_missing_examples_skipped_when_no_properties_key() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="ping",
                description="Health-check ping that returns ok status.",
                parameters={"type": "object"},
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "missing-examples" for i in report.issues)


# --- name-description-mismatch ---


def test_name_description_mismatch_fires_when_tokens_absent() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="search_documents",
                description="Return weather for a city by name.",
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert any(i.rule == "name-description-mismatch" for i in report.issues)


def test_name_description_mismatch_skipped_when_tokens_present() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="search_documents",
                description="Search documents in the index by keyword query.",
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "name-description-mismatch" for i in report.issues)


def test_name_description_mismatch_skipped_for_empty_description() -> None:
    catalog = ToolCatalog(
        tools=[ToolDefinition(name="search_documents", description="")]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "name-description-mismatch" for i in report.issues)
    assert any(i.rule == "missing-description" for i in report.issues)


def test_name_description_mismatch_skipped_for_short_name_tokens() -> None:
    # Tokens of length <= 2 are ignored; no distinctive tokens → no mismatch.
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="ab_cd",
                description="Completely unrelated weather lookup for a city.",
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "name-description-mismatch" for i in report.issues)


def test_name_description_mismatch_half_threshold_one_of_two_ok() -> None:
    # Two distinctive tokens; only one missing → missing*2 == len, not greater → no fire.
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="search_documents",
                description="Search the catalog by keyword and return matches.",
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert not any(i.rule == "name-description-mismatch" for i in report.issues)


def test_name_description_mismatch_hyphenated_name() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="fetch-invoice",
                description="Return the current outdoor temperature for a city.",
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert any(i.rule == "name-description-mismatch" for i in report.issues)


# --- lint catalog edge cases ---


def test_lint_empty_catalog_passes() -> None:
    report = lint_tool_descriptions(ToolCatalog(tools=[]))
    assert report.passed
    assert report.issues == []
    assert report.error_count == 0
    assert report.warning_count == 0


def test_lint_multiple_tools_mixed_findings() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(name="broken", description=""),
            ToolDefinition(
                name="search_documents",
                description="Return weather for a city by name today.",
            ),
            ToolDefinition(
                name="create_ticket",
                description="Create a support ticket in the helpdesk system.",
                parameters={
                    "properties": {
                        "title": {"type": "string", "description": "Ticket title"},
                    }
                },
            ),
        ]
    )
    report = lint_tool_descriptions(catalog)
    rules = {i.rule for i in report.issues}
    assert "missing-description" in rules
    assert "name-description-mismatch" in rules
    assert "missing-examples" in rules
    assert report.error_count >= 1
    assert not report.passed


# --- validate-spec / load suite ---


def test_validate_suite_structure_happy_path() -> None:
    suite = EvalSuite(
        name="ok",
        cases=[
            EvalCase(
                id="c1",
                request="Search docs about revenue",
                expected_tool=ToolExpectation(name="search_documents"),
            )
        ],
    )
    report = validate_suite_structure(suite)
    assert report.passed
    assert report.case_results[0].status == "skipped"


def test_validate_suite_structure_duplicate_ids_fail() -> None:
    suite = EvalSuite(
        name="dupes",
        cases=[
            EvalCase(
                id="c1",
                request="Search docs",
                expected_tool=ToolExpectation(name="search_documents"),
            ),
            EvalCase(
                id="c1",
                request="Fetch one doc",
                expected_tool=ToolExpectation(name="fetch_document"),
            ),
        ],
    )
    report = validate_suite_structure(suite)
    assert not report.passed
    assert any("Duplicate" in r.message for r in report.case_results)


def test_validate_suite_structure_empty_request_fails() -> None:
    suite = EvalSuite(
        name="empty-req",
        cases=[
            EvalCase(
                id="c1",
                request="   ",
                expected_tool=ToolExpectation(name="search_documents"),
            )
        ],
    )
    report = validate_suite_structure(suite)
    assert not report.passed
    assert report.case_results[0].status == "fail"


def test_validate_suite_structure_empty_expected_tool_fails() -> None:
    suite = EvalSuite(
        name="empty-tool",
        cases=[
            EvalCase(
                id="c1",
                request="Search docs about revenue",
                expected_tool=ToolExpectation(name=""),
            )
        ],
    )
    report = validate_suite_structure(suite)
    assert not report.passed
    assert "empty" in report.case_results[0].message.lower()


def test_load_eval_suite_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SpecValidationError, match="not found"):
        load_eval_suite(tmp_path / "missing.yaml")


def test_load_eval_suite_non_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / "suite.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SpecValidationError, match="mapping"):
        load_eval_suite(path)


def test_load_eval_suite_invalid_schema_raises(tmp_path: Path) -> None:
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.dump({"name": "x", "pass_threshold": 2.0}), encoding="utf-8")
    with pytest.raises(SpecValidationError, match="Invalid eval suite"):
        load_eval_suite(path)


def test_load_tool_catalog_happy_and_errors(tmp_path: Path) -> None:
    good = tmp_path / "tools.yaml"
    good.write_text(
        yaml.dump(
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo the provided message back to the caller.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog = load_tool_catalog(good)
    assert len(catalog.tools) == 1
    assert catalog.tools[0].name == "echo"

    with pytest.raises(SpecValidationError, match="not found"):
        load_tool_catalog(tmp_path / "nope.yaml")

    bad = tmp_path / "bad.yaml"
    bad.write_text("[]\n", encoding="utf-8")
    with pytest.raises(SpecValidationError, match="mapping"):
        load_tool_catalog(bad)


# --- KeywordSelector / mock eval ---


def test_keyword_selector_empty_tools_raises() -> None:
    with pytest.raises(EvalRunError, match="No tools"):
        KeywordSelector().select("search documents", [])


def test_keyword_selector_picks_best_overlap() -> None:
    tools = [
        ToolDefinition(name="search_documents", description="Search documents by keyword."),
        ToolDefinition(name="fetch_document", description="Retrieve one document by id."),
    ]
    name, args = KeywordSelector().select("Search documents about revenue", tools)
    assert name == "search_documents"
    assert args == {}


def test_run_eval_suite_wrong_tool_fails() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(name="search_documents", description="Search documents by keyword."),
            ToolDefinition(name="get_weather", description="Return weather for a city name."),
        ]
    )
    suite = EvalSuite(
        name="mismatch",
        cases=[
            EvalCase(
                id="weather-as-search",
                request="Return weather for a city name",
                expected_tool=ToolExpectation(name="search_documents"),
            )
        ],
        pass_threshold=1.0,
    )
    report, metrics = run_eval_suite(suite, catalog, KeywordSelector(), samples=1)
    assert metrics.selection_accuracy == 0.0
    assert not report.passed
    assert report.case_results[0].status == "fail"


def test_run_eval_suite_threshold_gates_pass() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(name="search_documents", description="Search documents by keyword."),
            ToolDefinition(name="fetch_document", description="Retrieve one document by id."),
        ]
    )
    suite = EvalSuite(
        name="thresh",
        cases=[
            EvalCase(
                id="ok",
                request="Search documents about revenue",
                expected_tool=ToolExpectation(name="search_documents"),
            ),
            EvalCase(
                id="bad",
                request="Retrieve one document by id",
                expected_tool=ToolExpectation(name="search_documents"),
            ),
        ],
        pass_threshold=0.9,
    )
    report, metrics = run_eval_suite(suite, catalog, KeywordSelector(), samples=1)
    assert metrics.selection_accuracy == 0.5
    assert not report.passed

    report_low, _ = run_eval_suite(
        suite, catalog, KeywordSelector(), samples=1, pass_threshold=0.4
    )
    assert report_low.passed


# --- discover / catalog helpers (no network) ---


def test_discover_catalog_transport_loads_fixture(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.yaml"
    tools_path.write_text(
        yaml.dump(
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo the provided message back to the caller.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = ServerConfig(name="local", transport="catalog", catalog=str(tools_path))
    catalog = discover_tools(config)
    assert len(catalog.tools) == 1
    assert catalog.tools[0].name == "echo"


def test_discover_catalog_requires_path() -> None:
    config = ServerConfig(name="local", transport="catalog", catalog=None)
    with pytest.raises(DiscoveryError, match="catalog"):
        discover_tools(config)


def test_discover_unknown_transport_raises() -> None:
    config = ServerConfig(name="local", transport="udp")
    with pytest.raises(DiscoveryError, match="Unknown transport"):
        discover_tools(config)


def test_load_server_config_missing_and_invalid(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="not found"):
        load_server_config(tmp_path / "missing.yaml")

    bad = tmp_path / "server.yaml"
    bad.write_text("[]\n", encoding="utf-8")
    with pytest.raises(DiscoveryError, match="mapping"):
        load_server_config(bad)


def test_discover_catalog_relative_path_uses_base_dir(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.yaml"
    tools_path.write_text(
        yaml.dump(
            {
                "tools": [
                    {
                        "name": "ping",
                        "description": "Health-check ping that returns ok status.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = ServerConfig(name="local", transport="catalog", catalog="tools.yaml")
    catalog = discover_tools(config, base_dir=tmp_path)
    assert {t.name for t in catalog.tools} == {"ping"}
