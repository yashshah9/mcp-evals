"""Stdio MCP framing must use Content-Length as bytes, not characters."""

from __future__ import annotations

import json
from io import BytesIO

from mcp_evals.mcp_client.stdio import _read_message, _write_message


def test_read_message_non_ascii_content_length() -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "café", "description": "日本語ツール"}]},
    }
    raw = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    assert len(raw) > len(raw.decode("utf-8"))  # multi-byte chars present
    stream = BytesIO(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    parsed = _read_message(stream)
    assert parsed["result"]["tools"][0]["name"] == "café"
    assert "日本語" in parsed["result"]["tools"][0]["description"]


def test_write_message_content_length_is_bytes() -> None:
    buf = BytesIO()
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {"note": "café"}}
    _write_message(buf, msg)
    data = buf.getvalue()
    header, _, body = data.partition(b"\r\n\r\n")
    length = int(header.decode("ascii").split(":", 1)[1].strip())
    assert length == len(body)
    assert json.loads(body.decode("utf-8"))["params"]["note"] == "café"


def test_read_message_rejects_truncated_body() -> None:
    from mcp_evals.errors import DiscoveryError
    import pytest

    stream = BytesIO(b"Content-Length: 20\r\n\r\n{\"short\":1}")
    with pytest.raises(DiscoveryError, match="mid-message"):
        _read_message(stream)
