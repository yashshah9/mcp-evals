"""Domain-specific exceptions."""


class McpEvalsError(Exception):
    """Base error for mcp-evals."""


class SpecValidationError(McpEvalsError):
    """Eval specification is invalid."""


class LintError(McpEvalsError):
    """Description linting found blocking issues."""
