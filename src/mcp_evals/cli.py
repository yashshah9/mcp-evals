"""Command-line interface for mcp-evals."""

from __future__ import annotations

import json
import os
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
from mcp_evals.mcp_client.discover import discover_tools, load_server_config
from mcp_evals.runner.eval_runner import validate_suite_structure
from mcp_evals.runner.llm_runner import KeywordSelector, OpenAICompatibleSelector, run_eval_suite
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


def _print_lint(report: object, fmt: str, fail_on_warning: bool) -> None:
    if fmt == "json":
        payload = {
            "passed": report.passed,  # type: ignore[attr-defined]
            "errors": report.error_count,  # type: ignore[attr-defined]
            "warnings": report.warning_count,  # type: ignore[attr-defined]
            "issues": [issue.__dict__ for issue in report.issues],  # type: ignore[attr-defined]
        }
        console.print_json(json.dumps(payload))
    else:
        table = Table(title="Description Lint Report")
        table.add_column("Severity")
        table.add_column("Rule")
        table.add_column("Tool")
        table.add_column("Message")
        for issue in report.issues:  # type: ignore[attr-defined]
            color = "red" if issue.severity == "error" else "yellow"
            table.add_row(
                f"[{color}]{issue.severity}[/{color}]",
                issue.rule,
                issue.tool,
                issue.message,
            )
        console.print(table)
        console.print(
            f"\n{report.error_count} error(s), {report.warning_count} warning(s)"  # type: ignore[attr-defined]
        )
    if not report.passed or (fail_on_warning and report.warning_count):  # type: ignore[attr-defined]
        sys.exit(1)


@main.command("lint")
@click.argument("catalog", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--live", "server_config", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--fail-on-warning", is_flag=True, help="Exit non-zero on warnings too")
def lint_cmd(
    catalog: Path | None,
    server_config: Path | None,
    fmt: str,
    fail_on_warning: bool,
) -> None:
    """Lint MCP tool descriptions from a YAML catalog or a live server config."""
    try:
        if server_config:
            config = load_server_config(server_config)
            tool_catalog = discover_tools(config, base_dir=server_config.parent)
        elif catalog:
            tool_catalog = load_tool_catalog(catalog)
        else:
            raise click.UsageError("Provide a catalog file or --live SERVER.yaml")
        report = lint_tool_descriptions(tool_catalog)
    except McpEvalsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)
    _print_lint(report, fmt, fail_on_warning)


@main.command("discover")
@click.argument("server_config", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def discover_cmd(server_config: Path, fmt: str) -> None:
    """List tools from an MCP server config (stdio, http, sse, or catalog fixture)."""
    try:
        config = load_server_config(server_config)
        catalog = discover_tools(config, base_dir=server_config.parent)
    except McpEvalsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)
    if fmt == "json":
        console.print_json(json.dumps(catalog.model_dump()))
        return
    console.print(f"[bold]{config.name}[/bold] — {len(catalog.tools)} tool(s)")
    for tool in catalog.tools:
        desc = tool.description or "(no description)"
        console.print(f"  • {tool.name}: {desc}")


@main.command("validate-spec")
@click.argument("suite", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def validate_spec_cmd(suite: Path, fmt: str) -> None:
    """Validate an eval suite YAML file."""
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


@main.command("run")
@click.argument("suite", type=click.Path(exists=True, path_type=Path))
@click.option("--catalog", type=click.Path(exists=True, path_type=Path))
@click.option("--live", "server_config", type=click.Path(exists=True, path_type=Path))
@click.option("--model", default="mock", help="mock | openai-compatible model name")
@click.option("--base-url", default=None, help="OpenAI-compatible base URL (Ollama: http://localhost:11434/v1)")
@click.option("--samples", default=1, type=click.IntRange(1, 100))
@click.option("--pass-threshold", "threshold", default=None, type=float)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def run_cmd(
    suite: Path,
    catalog: Path | None,
    server_config: Path | None,
    model: str,
    base_url: str | None,
    samples: int,
    threshold: float | None,
    fmt: str,
) -> None:
    """Run behavioral evals against a tool catalog or a live MCP server."""
    settings = get_settings()
    try:
        eval_suite = load_eval_suite(suite)
        if server_config:
            config = load_server_config(server_config)
            tool_catalog = discover_tools(config, base_dir=server_config.parent)
        elif catalog:
            tool_catalog = load_tool_catalog(catalog)
        else:
            raise click.UsageError("Provide --catalog FILE or --live SERVER.yaml")
        if model == "mock":
            selector: KeywordSelector | OpenAICompatibleSelector = KeywordSelector()
        else:
            selector = OpenAICompatibleSelector(
                base_url=base_url or "https://api.openai.com/v1",
                model=model,
                api_key=os.environ.get("OPENAI_API_KEY"),
            )
        report, metrics = run_eval_suite(
            eval_suite,
            tool_catalog,
            selector,
            samples=samples,
            pass_threshold=threshold if threshold is not None else settings.pass_threshold,
        )
    except McpEvalsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)

    if fmt == "json":
        console.print_json(
            json.dumps(
                {
                    "suite": report.suite_name,
                    "passed": report.passed,
                    "accuracy": metrics.selection_accuracy,
                    "argument_validity": metrics.argument_validity,
                    "cases": [r.__dict__ for r in report.case_results],
                }
            )
        )
    else:
        table = Table(title=f"Eval: {report.suite_name}")
        table.add_column("Case")
        table.add_column("Status")
        table.add_column("Detail")
        for result in report.case_results:
            color = "green" if result.status == "pass" else "red"
            table.add_row(result.case_id, f"[{color}]{result.status}[/{color}]", result.message)
        console.print(table)
        if model == "mock":
            console.print(
                f"accuracy={metrics.selection_accuracy:.0%} "
                f"threshold={report.threshold:.0%} "
                "(mock selector scores tool names only)"
            )
        else:
            console.print(
                f"accuracy={metrics.selection_accuracy:.0%} "
                f"args={metrics.argument_validity:.0%} "
                f"threshold={report.threshold:.0%}"
            )
    if not report.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
