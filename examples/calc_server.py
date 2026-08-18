#!/usr/bin/env python3
"""Minimal stdio MCP server used as a discovery fixture.

Speaks the MCP JSON-RPC framing (Content-Length headers) and exposes
two tools so mcp-evals can handshake without a third-party SDK.
"""

from __future__ import annotations

import json
import sys
from typing import Any

TOOLS = [
    {
        "name": "add",
        "description": "Add two numbers and return the sum.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Left operand"},
                "b": {"type": "number", "description": "Right operand"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "echo",
        "description": "Echo a text message back to the caller.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Text to echo"},
            },
            "required": ["message"],
        },
    },
]


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.readline()
        if line == "":
            return None
        stripped = line.strip()
        if stripped == "":
            break
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = sys.stdin.read(length)
    return json.loads(body)


def _write_message(message: dict[str, Any]) -> None:
    raw = json.dumps(message)
    sys.stdout.write(f"Content-Length: {len(raw.encode())}\r\n\r\n{raw}")
    sys.stdout.flush()


def main() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            return
        method = msg.get("method")
        req_id = msg.get("id")
        if method == "initialize":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "calc-server", "version": "0.1.0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _write_message({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                }
            )
        elif req_id is not None:
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method {method}"},
                }
            )


if __name__ == "__main__":
    main()
