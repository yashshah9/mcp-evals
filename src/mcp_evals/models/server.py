"""MCP server connection configuration."""

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """How to reach an MCP server for discovery."""

    name: str = "mcp-server"
    transport: str = Field(
        default="stdio",
        description="stdio | http | sse | streamable-http | catalog",
    )
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    catalog: str | None = None
    timeout_seconds: float = 8.0
