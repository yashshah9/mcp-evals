"""Command-line interface for mcp-evals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from mcp_evals import __version__
from mcp_evals.config import get_settings
from mcp_evals.errors import McpEvalsError
from mcp_evals.linter.descriptions import lint_tool_descriptions
from mcp_evals.logging import configure_logging
from mcp_evals.runner.eval_runner import validate_suite_structure
from mcp_evals.spec_loader import load_eval_suite, load_tool_catalog

console = Console()


@click.group()
@click.version_option(__version__, prog_name="mcp-evals")
@click.option("--log-level", default=None, help="Override MCP_EVALS_LOG_LEVEL")
@click.option("--json-logs", is_flag=True, help="Emit JSON logs")
@click.pass_context
def main(ctx: click.Context, log_level: str | None, json_logs: bool) -> None:
    """Behavioral evaluation and description linting for MCP servers."""
    settings = get_settings()
    configure_logging(level=log_level or settings.log_level, json_output=json_logs)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings


@main.command("health")
def health() -> None:
    """Verify installation and configuration."""
    settings = get_settings()
    console.print(f"[green]mcp-evals {__version__} OK[/green]")
    console.print(f"  default_model: {settings.default_model}")
    console.print(f"  pass_threshold: {settings.pass_threshold}")


@main.command("lint")
@click.argument("catalog", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--fail-on-warning", is_flag=True, help="Exit non-zero on warnings too")
def lint_cmd(catalog: Path, fmt: str, fail_on_warning: bool) -> None:
    """Lint MCP tool descriptions from a YAML tool catalog fixture."""
    try:
        tool_catalog = load_tool_catalog(catalog)
        report = lint_tool_descriptions(tool_catalog)
    except McpEvalsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)

    if fmt == "json":
        payload = {
            "passed": report.passed,
            "errors": report.error_count,
            "warnings": report.warning_count,
            "issues": [issue.__dict__ for issue in report.issues],
        }
        console.print_json(json.dumps(payload))
    else:
        table = Table(title="Description Lint Report")
        table.add_column("Severity")
        table.add_column("Rule")
        table.add_column("Tool")
        table.add_column("Message")
        for issue in report.issues:
            color = "red" if issue.severity == "error" else "yellow"
            table.add_row(
                f"[{color}]{issue.severity}[/{color}]",
                issue.rule,
                issue.tool,
                issue.message,
            )
        console.print(table)
        console.print(
            f"\n{report.error_count} error(s), {report.warning_count} warning(s)"
        )

    if not report.passed or (fail_on_warning and report.warning_count):
        sys.exit(1)


@main.command("validate-spec")
@click.argument("suite", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def validate_spec_cmd(suite: Path, fmt: str) -> None:
    """Validate an eval suite YAML file (structure only in v0.1)."""
    try:
        eval_suite = load_eval_suite(suite)
        report = validate_suite_structure(eval_suite)
    except McpEvalsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)

    if fmt == "json":
        payload = {
            "suite": report.suite_name,
            "mode": report.mode,
            "passed": report.passed,
            "cases": [r.__dict__ for r in report.case_results],
        }
        console.print_json(json.dumps(payload))
    else:
        console.print(f"Suite: [bold]{report.suite_name}[/bold] ({report.mode})")
        for result in report.case_results:
            color = {"pass": "green", "fail": "red", "skipped": "yellow"}.get(
                result.status, "white"
            )
            console.print(f"  [{color}]{result.case_id}[/{color}]: {result.message}")

    if not report.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
