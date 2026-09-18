"""Unit tests for Streamable HTTP / SSE MCP discovery (mocked httpx)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from mcp_evals.errors import DiscoveryError
from mcp_evals.mcp_client.discover import discover_tools
from mcp_evals.mcp_client.sse import _parse_sse_messages, discover_sse
from mcp_evals.models.server import ServerConfig

TOOLS = [
    {
        "name": "add",
        "description": "Add two numbers.",
        "inputSchema": {"type": "object", "properties": {"a": {}, "b": {}}},
    },
    {
        "name": "echo",
        "description": "Echo text.",
        "inputSchema": {"type": "object", "properties": {"message": {}}},
    },
]


def _sse_frame(payload: dict[str, Any]) -> str:
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


def test_parse_sse_messages_data_events() -> None:
    body = (
        "event: message\n"
        'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n'
        "\n"
        ": keep-alive\n"
        "\n"
        'data: {"jsonrpc":"2.0","id":2,"result":{"tools":[]}}\n'
        "\n"
    )
    msgs = _parse_sse_messages(body)
    assert len(msgs) == 2
    assert msgs[0]["id"] == 1
    assert msgs[1]["id"] == 2


def test_discover_sse_initialize_and_tools_list() -> None:
    session = "sess-test-1"
    seen_session_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        msg = json.loads(request.content.decode())
        seen_session_headers.append(request.headers.get("mcp-session-id"))
        method = msg.get("method")
        req_id = msg.get("id")

        if method == "initialize":
            body = _sse_frame(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "calc-sse", "version": "0.7.0"},
                    },
                }
            )
            return httpx.Response(
                200,
                headers={
                    "Content-Type": "text/event-stream",
                    "Mcp-Session-Id": session,
                },
                content=body.encode(),
            )

        if method == "notifications/initialized":
            assert request.headers.get("mcp-session-id") == session
            return httpx.Response(202)

        if method == "tools/list":
            assert request.headers.get("mcp-session-id") == session
            body = _sse_frame(
                {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            )
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                content=body.encode(),
            )

        return httpx.Response(500, text=f"unexpected {method}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=3.0) as client:
        catalog = discover_sse("http://mcp.test/mcp", client=client)

    assert {t.name for t in catalog.tools} == {"add", "echo"}
    # initialize has no session yet; later calls echo Mcp-Session-Id
    assert seen_session_headers[0] is None
    assert session in seen_session_headers[1:]


def test_discover_tools_sse_and_streamable_http_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_discover_sse(url: str, timeout: float = 8.0, **kwargs: Any) -> Any:
        calls.append(url)
        from mcp_evals.models.spec import ToolCatalog, ToolDefinition

        return ToolCatalog(tools=[ToolDefinition(name="echo", description="Echo.")])

    monkeypatch.setattr("mcp_evals.mcp_client.sse.discover_sse", fake_discover_sse)

    for transport in ("sse", "streamable-http"):
        config = ServerConfig(name="t", transport=transport, url="http://mcp.test/mcp")
        catalog = discover_tools(config)
        assert catalog.tools[0].name == "echo"

    assert calls == ["http://mcp.test/mcp", "http://mcp.test/mcp"]


def test_discover_tools_sse_requires_url() -> None:
    config = ServerConfig(name="t", transport="sse", url=None)
    with pytest.raises(DiscoveryError, match="requires 'url'"):
        discover_tools(config)


def test_discover_sse_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    transport = httpx.MockTransport(handler)
    with (
        httpx.Client(transport=transport, timeout=1.0) as client,
        pytest.raises(DiscoveryError, match="HTTP 503"),
    ):
        discover_sse("http://mcp.test/mcp", client=client)
