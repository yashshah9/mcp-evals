"""JSON-RPC MCP client over HTTP POST (streamable-HTTP subset)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from mcp_evals import __version__
from mcp_evals.errors import DiscoveryError
from mcp_evals.mcp_client.stdio import _to_tool
from mcp_evals.models.spec import ToolCatalog

_SESSION_HEADER = "mcp-session-id"


def discover_http(url: str, timeout: float = 8.0) -> ToolCatalog:
    """Initialize a JSON-RPC HTTP MCP endpoint and return tools/list.

    Echoes ``Mcp-Session-Id`` when the server assigns one (same as SSE client).
    """
    if not url:
        raise DiscoveryError("http transport requires 'url'.")

    session_id: str | None = None

    def headers() -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if session_id:
            h["Mcp-Session-Id"] = session_id
        return h

    def _capture_session(resp: Any) -> None:
        nonlocal session_id
        sid = resp.headers.get(_SESSION_HEADER) or resp.headers.get("Mcp-Session-Id")
        if sid:
            session_id = sid

    def rpc(method: str, params: dict[str, Any] | None, request_id: int) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _capture_session(resp)
                body = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise DiscoveryError(f"HTTP MCP request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise DiscoveryError(f"HTTP MCP returned invalid JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise DiscoveryError(f"{method} returned a non-object JSON message.")
        if "error" in body:
            raise DiscoveryError(f"{method} failed: {body['error']}")
        return body

    init = rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-evals", "version": __version__},
        },
        1,
    )
    if "result" not in init:
        raise DiscoveryError("initialize returned no result.")

    notify_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    notify_req = urllib.request.Request(
        url,
        data=json.dumps(notify_payload).encode(),
        headers=headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(notify_req, timeout=timeout) as resp:
            _capture_session(resp)
            resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code >= 400 and exc.code not in {202, 204}:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise DiscoveryError(
                f"notifications/initialized failed: HTTP {exc.code} {detail}"
            ) from exc
    except urllib.error.URLError as exc:
        raise DiscoveryError(f"notifications/initialized failed: {exc}") from exc

    listed = rpc("tools/list", {}, 2)
    tools_raw = listed.get("result", {}).get("tools", [])
    tools = [_to_tool(t) for t in tools_raw if isinstance(t, dict)]
    return ToolCatalog(tools=tools)
