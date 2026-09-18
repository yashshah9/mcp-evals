"""HTTP MCP client must echo Mcp-Session-Id across the handshake."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp_evals.mcp_client.http import discover_http


def test_discover_http_echoes_session_id() -> None:
    seen: list[str | None] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode())
            seen.append(self.headers.get("Mcp-Session-Id"))
            method = body.get("method")
            if method == "initialize":
                payload = {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
                }
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "sess-abc")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if method == "notifications/initialized":
                self.send_response(202)
                self.send_header("Mcp-Session-Id", "sess-abc")
                self.end_headers()
                return
            if method == "tools/list":
                if self.headers.get("Mcp-Session-Id") != "sess-abc":
                    self.send_response(401)
                    self.end_headers()
                    return
                payload = {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"tools": [{"name": "ping", "description": "pong"}]},
                }
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(400)
            self.end_headers()

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        catalog = discover_http(f"http://{host}:{port}", timeout=3)
        assert {t.name for t in catalog.tools} == {"ping"}
        # initialize: no session yet; notify + tools/list must echo it
        assert seen[0] is None
        assert seen[1] == "sess-abc"
        assert seen[2] == "sess-abc"
    finally:
        httpd.shutdown()
        httpd.server_close()
