"""Minimal MCP JSON-RPC client over stdio."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, BinaryIO, cast

from mcp_evals import __version__
from mcp_evals.errors import DiscoveryError
from mcp_evals.models.spec import ToolCatalog, ToolDefinition


def _rpc(method: str, params: dict[str, Any] | None, request_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _write_message(stdin: BinaryIO, message: dict[str, Any]) -> None:
    raw = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stdin.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    stdin.flush()


def _read_headers(stdout: BinaryIO) -> dict[str, str]:
    headers: dict[str, str] = {}
    while True:
        line = stdout.readline()
        if line == b"":
            raise DiscoveryError("MCP server closed stdout during handshake.")
        if line in (b"\r\n", b"\n"):
            break
        stripped = line.decode("ascii", errors="replace").strip()
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


def _read_message(stdout: BinaryIO) -> dict[str, Any]:
    headers = _read_headers(stdout)
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        raise DiscoveryError("MCP server sent a message without Content-Length.")
    # Content-Length is bytes — read exactly that many from the binary pipe.
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        chunk = stdout.read(remaining)
        if not chunk:
            raise DiscoveryError("MCP server closed stdout mid-message.")
        chunks.append(chunk)
        remaining -= len(chunk)
    body = b"".join(chunks)
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise DiscoveryError("MCP server returned a non-object JSON message.")
    return parsed


def _to_tool(raw: dict[str, Any]) -> ToolDefinition:
    schema = raw.get("inputSchema") or raw.get("input_schema") or {}
    if not isinstance(schema, dict):
        schema = {}
    return ToolDefinition(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        parameters=schema,
    )


def discover_stdio(
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
    timeout: float = 8.0,
) -> ToolCatalog:
    """Initialize a stdio MCP server and return tools/list."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=merged_env,
        )
    except OSError as exc:
        raise DiscoveryError(f"Failed to start MCP server '{command}': {exc}") from exc

    try:
        assert proc.stdin is not None and proc.stdout is not None
        stdin = cast(BinaryIO, proc.stdin)
        stdout = cast(BinaryIO, proc.stdout)
        _write_message(
            stdin,
            _rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-evals", "version": __version__},
                },
                1,
            ),
        )
        init = _read_message(stdout)
        if "error" in init:
            raise DiscoveryError(f"initialize failed: {init['error']}")
        _write_message(
            stdin,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        _write_message(stdin, _rpc("tools/list", {}, 2))
        listed = _read_message(stdout)
        if "error" in listed:
            raise DiscoveryError(f"tools/list failed: {listed['error']}")
        tools_raw = listed.get("result", {}).get("tools", [])
        tools = [_to_tool(t) for t in tools_raw if isinstance(t, dict)]
        return ToolCatalog(tools=tools)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(f"MCP handshake failed: {exc}") from exc
    finally:
        proc.kill()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
