"""Static analysis for MCP tool descriptions."""

from dataclasses import dataclass, field

from mcp_evals.models.spec import ToolCatalog, ToolDefinition


@dataclass
class LintIssue:
    """A single lint finding."""

    rule: str
    severity: str  # error | warning
    tool: str
    message: str


@dataclass
class LintReport:
    """Aggregated lint results."""

    issues: list[LintIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.error_count == 0


def _tokenize(text: str) -> set[str]:
    return {word.lower() for word in text.replace("_", " ").split() if len(word) > 2}


def lint_tool_descriptions(catalog: ToolCatalog) -> LintReport:
    """Run static checks on tool descriptions."""
    report = LintReport()
    tools = catalog.tools

    for tool in tools:
        _check_missing_description(tool, report)
        _check_short_description(tool, report)
        _check_missing_param_docs(tool, report)
        _check_required_param_docs(tool, report)
        _check_name_description_mismatch(tool, report)

    _check_overlapping_descriptions(tools, report)
    _check_ambiguous_verbs(tools, report)
    return report


def _name_tokens(name: str) -> set[str]:
    parts = name.replace("-", "_").split("_")
    return {p.lower() for p in parts if len(p) > 2}


def _check_name_description_mismatch(tool: ToolDefinition, report: LintReport) -> None:
    """Warn when distinctive name tokens never appear in the description."""
    if not tool.description.strip():
        return
    name_toks = _name_tokens(tool.name)
    if not name_toks:
        return
    desc_toks = _tokenize(tool.description)
    missing = sorted(name_toks - desc_toks)
    # Require at least half of distinctive name tokens to appear in the description.
    if len(missing) * 2 > len(name_toks):
        report.issues.append(
            LintIssue(
                rule="name-description-mismatch",
                severity="warning",
                tool=tool.name,
                message=(
                    f"Tool name tokens {missing} never appear in the description; "
                    "agents may not map the request to this tool."
                ),
            )
        )


def _check_missing_description(tool: ToolDefinition, report: LintReport) -> None:
    if not tool.description.strip():
        report.issues.append(
            LintIssue(
                rule="missing-description",
                severity="error",
                tool=tool.name,
                message="Tool has no description; agents cannot select it reliably.",
            )
        )


def _check_short_description(tool: ToolDefinition, report: LintReport) -> None:
    if 0 < len(tool.description.strip()) < 20:
        report.issues.append(
            LintIssue(
                rule="short-description",
                severity="warning",
                tool=tool.name,
                message="Description is very short; add when-to-use guidance.",
            )
        )


def _check_missing_param_docs(tool: ToolDefinition, report: LintReport) -> None:
    props = tool.parameters.get("properties", {})
    if not isinstance(props, dict):
        return
    for param_name, param_schema in props.items():
        if not isinstance(param_schema, dict):
            continue
        if not str(param_schema.get("description", "")).strip():
            report.issues.append(
                LintIssue(
                    rule="missing-param-description",
                    severity="warning",
                    tool=tool.name,
                    message=f"Parameter '{param_name}' has no description.",
                )
            )


def _check_required_param_docs(tool: ToolDefinition, report: LintReport) -> None:
    required = tool.parameters.get("required", [])
    props = tool.parameters.get("properties", {})
    if not isinstance(required, list) or not isinstance(props, dict):
        return
    for name in required:
        schema = props.get(name, {})
        if not isinstance(schema, dict):
            report.issues.append(
                LintIssue(
                    rule="required-params-undocumented",
                    severity="error",
                    tool=tool.name,
                    message=f"Required parameter '{name}' is missing from properties.",
                )
            )
            continue
        if not str(schema.get("description", "")).strip() or "type" not in schema:
            report.issues.append(
                LintIssue(
                    rule="required-params-undocumented",
                    severity="error",
                    tool=tool.name,
                    message=f"Required parameter '{name}' needs a type and description.",
                )
            )


def _check_ambiguous_verbs(tools: list[ToolDefinition], report: LintReport) -> None:
    verbs = ("get", "fetch", "list", "search", "find", "query")
    buckets: dict[str, list[str]] = {verb: [] for verb in verbs}
    for tool in tools:
        blob = f"{tool.name} {tool.description}".lower()
        for verb in verbs:
            if verb in blob.split() or tool.name.lower().startswith(verb):
                buckets[verb].append(tool.name)
    for verb, names in buckets.items():
        unique = sorted(set(names))
        if len(unique) >= 2:
            report.issues.append(
                LintIssue(
                    rule="ambiguous-verbs",
                    severity="warning",
                    tool=unique[0],
                    message=(
                        f"Tools {unique} share the verb '{verb}'; "
                        "agents may pick the wrong one."
                    ),
                )
            )


def _check_overlapping_descriptions(tools: list[ToolDefinition], report: LintReport) -> None:
    for i, left in enumerate(tools):
        left_tokens = _tokenize(left.description)
        if not left_tokens:
            continue
        for right in tools[i + 1 :]:
            right_tokens = _tokenize(right.description)
            if not right_tokens:
                continue
            overlap = left_tokens & right_tokens
            ratio = len(overlap) / min(len(left_tokens), len(right_tokens))
            if ratio >= 0.6:
                report.issues.append(
                    LintIssue(
                        rule="overlapping-descriptions",
                        severity="warning",
                        tool=left.name,
                        message=(
                            f"Descriptions overlap heavily with '{right.name}' "
                            f"({len(overlap)} shared terms); agents may confuse them."
                        ),
                    )
                )
