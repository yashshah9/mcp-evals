from typing import Any

from mcp_evals.mcp_client.discover import discover_tools, load_server_config
from mcp_evals.mcp_client.http import discover_http
from mcp_evals.mcp_client.stdio import discover_stdio

__all__ = [
    "discover_http",
    "discover_sse",
    "discover_stdio",
    "discover_tools",
    "load_server_config",
]


def __getattr__(name: str) -> Any:
    if name == "discover_sse":
        from mcp_evals.mcp_client.sse import discover_sse

        return discover_sse
    raise AttributeError(name)
