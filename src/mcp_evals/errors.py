"""Domain-specific exceptions."""


class McpEvalsError(Exception):
    """Base error for mcp-evals."""


class SpecValidationError(McpEvalsError):
    """Eval specification is invalid."""


class LintError(McpEvalsError):
    """Description linting found blocking issues."""


class DiscoveryError(McpEvalsError):
    """Failed to discover tools from an MCP server."""


class EvalRunError(McpEvalsError):
    """Behavioral eval run failed."""
