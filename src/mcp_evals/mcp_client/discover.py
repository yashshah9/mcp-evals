"""Discover MCP tools from a server config or catalog fixture."""

from pathlib import Path

import yaml

from mcp_evals.errors import DiscoveryError, SpecValidationError
from mcp_evals.mcp_client.http import discover_http
from mcp_evals.mcp_client.stdio import discover_stdio
from mcp_evals.models.server import ServerConfig
from mcp_evals.models.spec import ToolCatalog
from mcp_evals.spec_loader import load_tool_catalog


def load_server_config(path: Path) -> ServerConfig:
    if not path.exists():
        raise DiscoveryError(f"Server config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DiscoveryError("Server config must be a YAML mapping.")
    return ServerConfig.model_validate(raw)


def discover_tools(config: ServerConfig, base_dir: Path | None = None) -> ToolCatalog:
    """Load tools via catalog fixture, stdio MCP, or HTTP (not yet)."""
    root = base_dir or Path.cwd()
    if config.transport == "catalog":
        if not config.catalog:
            raise DiscoveryError("catalog transport requires 'catalog' path.")
        catalog_path = Path(config.catalog)
        if not catalog_path.is_absolute():
            catalog_path = root / catalog_path
        try:
            return load_tool_catalog(catalog_path)
        except SpecValidationError as exc:
            raise DiscoveryError(str(exc)) from exc

    if config.transport == "stdio":
        if not config.command:
            raise DiscoveryError("stdio transport requires 'command'.")
        return discover_stdio(
            config.command,
            _resolve_args(root, config.args),
            env=config.env,
            timeout=config.timeout_seconds,
        )

    if config.transport == "http":
        if not config.url:
            raise DiscoveryError("http transport requires 'url'.")
        return discover_http(config.url, timeout=config.timeout_seconds)

    raise DiscoveryError(f"Unknown transport: {config.transport}")


def _resolve_args(root: Path, args: list[str]) -> list[str]:
    resolved: list[str] = []
    for arg in args:
        path = Path(arg)
        if path.is_absolute():
            resolved.append(arg)
            continue
        under_root = root / path
        if under_root.exists():
            resolved.append(str(under_root))
        elif (root / path.name).exists():
            resolved.append(str(root / path.name))
        else:
            resolved.append(arg)
    return resolved
