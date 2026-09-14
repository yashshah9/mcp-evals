"""Tests for description linter."""

from mcp_evals.linter.descriptions import lint_tool_descriptions
from mcp_evals.models.spec import ToolCatalog, ToolDefinition


def test_lint_flags_missing_description() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(name="broken", description=""),
            ToolDefinition(name="ok", description="Fetch a user profile by ID."),
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert report.error_count == 1
    assert report.issues[0].rule == "missing-description"


def test_lint_flags_overlapping_descriptions() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="search_a",
                description="Search documents by keyword query in the index.",
            ),
            ToolDefinition(
                name="search_b",
                description="Search documents by keyword query in database.",
            ),
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert any(i.rule == "overlapping-descriptions" for i in report.issues)


def test_lint_flags_required_param_docs() -> None:
    catalog = ToolCatalog(
        tools=[
            ToolDefinition(
                name="create_issue",
                description="Create a GitHub issue in the configured repository.",
                parameters={
                    "type": "object",
                    "required": ["title"],
                    "properties": {"title": {"type": "string"}},
                },
            )
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert any(i.rule == "required-params-undocumented" for i in report.issues)


def test_lint_passes_clean_catalog() -> None:
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
            ),
        ]
    )
    report = lint_tool_descriptions(catalog)
    assert report.passed


def test_lint_flags_name_description_mismatch() -> None:
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


def test_lint_flags_missing_examples() -> None:
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


def test_lint_passes_with_examples() -> None:
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