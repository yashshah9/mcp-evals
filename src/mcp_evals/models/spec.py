"""Eval specification models."""

from pydantic import BaseModel, Field


class ToolExpectation(BaseModel):
    """Expected tool selection for a single eval case."""

    name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class EvalCase(BaseModel):
    """One behavioral eval case: user request → expected tool."""

    id: str
    request: str
    expected_tool: ToolExpectation
    tags: list[str] = Field(default_factory=list)


class EvalSuite(BaseModel):
    """Collection of eval cases for an MCP server."""

    name: str
    description: str = ""
    cases: list[EvalCase] = Field(default_factory=list)
    pass_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class ToolDefinition(BaseModel):
    """Minimal MCP tool definition for linting."""

    name: str
    description: str = ""
    parameters: dict[str, object] = Field(default_factory=dict)


class ToolCatalog(BaseModel):
    """Discovered tools from an MCP server or fixture."""

    tools: list[ToolDefinition] = Field(default_factory=list)
