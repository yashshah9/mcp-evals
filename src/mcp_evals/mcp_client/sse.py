"""Streamable HTTP / SSE MCP discovery client (JSON-RPC over POST + event-stream)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from mcp_evals import __version__
from mcp_evals.errors import DiscoveryError
from mcp_evals.mcp_client.stdio import _to_tool
from mcp_evals.models.spec import ToolCatalog

_ACCEPT = "application/json, text/event-stream"
_SESSION_HEADER = "mcp-session-id"


def _parse_sse_messages(body: str) -> list[dict[str, Any]]:
    """Extract JSON objects from SSE `data:` lines (ignore other fields)."""
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal data_lines
        if not data_lines:
            return
        raw = "\n".join(data_lines)
        data_lines = []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(parsed, dict):
            messages.append(parsed)
        elif isinstance(parsed, list):
            messages.extend(m for m in parsed if isinstance(m, dict))

    for line in body.splitlines():
        if line == "":
            flush()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    flush()
    return messages


def _jsonrpc_from_response(response: httpx.Response, request_id: int) -> dict[str, Any]:
    content_type = (response.headers.get("content-type") or "").lower()
    text = response.text

    if "text/event-stream" in content_type or text.lstrip().startswith("data:"):
        messages = _parse_sse_messages(text)
        for msg in messages:
            if msg.get("id") == request_id:
                return msg
        raise DiscoveryError(
            f"SSE stream had no JSON-RPC response for id={request_id} "
            f"({len(messages)} event(s) parsed)."
        )

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise DiscoveryError(f"Streamable HTTP returned invalid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise DiscoveryError("Streamable HTTP returned a non-object JSON message.")
    return body


def discover_sse(
    url: str,
    timeout: float = 8.0,
    *,
    client: httpx.Client | None = None,
) -> ToolCatalog:
    """Initialize a Streamable HTTP MCP endpoint and return tools/list.

    Accepts both ``application/json`` and ``text/event-stream`` responses.
    Echoes ``Mcp-Session-Id`` when the server assigns one.
    """
    if not url:
        raise DiscoveryError("sse/streamable-http transport requires 'url'.")

    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    session_id: str | None = None

    def headers() -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": _ACCEPT,
        }
        if session_id:
            h["Mcp-Session-Id"] = session_id
        return h

    def rpc(method: str, params: dict[str, Any] | None, request_id: int) -> dict[str, Any]:
        nonlocal session_id
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            resp = http.post(url, content=json.dumps(payload), headers=headers())
        except httpx.HTTPError as exc:
            raise DiscoveryError(f"Streamable HTTP MCP request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise DiscoveryError(
                f"{method} HTTP {resp.status_code}: {resp.text[:200] or resp.reason_phrase}"
            )
        sid = resp.headers.get(_SESSION_HEADER) or resp.headers.get("Mcp-Session-Id")
        if sid:
            session_id = sid
        body = _jsonrpc_from_response(resp, request_id)
        if "error" in body:
            raise DiscoveryError(f"{method} failed: {body['error']}")
        return body

    def notify(method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        try:
            resp = http.post(url, content=json.dumps(payload), headers=headers())
        except httpx.HTTPError as exc:
            raise DiscoveryError(f"Streamable HTTP notification failed: {exc}") from exc
        # Spec: 202 Accepted (or ignore benign 2xx); errors still fail discovery.
        if resp.status_code >= 400:
            raise DiscoveryError(
                f"{method} HTTP {resp.status_code}: {resp.text[:200] or resp.reason_phrase}"
            )

    try:
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
        notify("notifications/initialized")
        listed = rpc("tools/list", {}, 2)
        tools_raw = listed.get("result", {}).get("tools", [])
        tools = [_to_tool(t) for t in tools_raw if isinstance(t, dict)]
        return ToolCatalog(tools=tools)
    finally:
        if owns_client:
            http.close()
