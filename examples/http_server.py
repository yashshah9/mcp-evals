#!/usr/bin/env python3
"""Minimal HTTP JSON-RPC MCP server used as a discovery fixture."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            msg = json.loads(raw.decode())
        except json.JSONDecodeError:
            self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"message": "invalid json"}})
            return
        method = msg.get("method")
        req_id = msg.get("id")
        if method == "initialize":
            self._send(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "calc-http", "version": "0.3.0"},
                    },
                },
            )
            return
        if method == "tools/list":
            self._send(200, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
            return
        self._send(
            200,
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown {method}"},
            },
        )

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    httpd = serve(port=8765)
    print(f"listening on http://127.0.0.1:{httpd.server_address[1]}", flush=True)
    httpd.serve_forever()
