#!/usr/bin/env python3
"""Expose the coding models and, on request, the existing read-only MCP endpoints."""

import argparse
import http.client
import json
import socket
import socketserver
from http.server import BaseHTTPRequestHandler
from pathlib import Path

MODEL = "research-code"
# Allowed model id -> context and output limits. Two production models
# (research-code = Gemma 4 26B-A4B QAT HauhauCS, story = Gemory 26B-A4B),
# both at the full 262144-token window with 8192 output tokens. Legacy
# profile names resolve to the same two weights inside the llama.cpp router.
MODEL_MODELS = {
    "research-code": {"context": 262144, "output": 8192},
    "story": {"context": 262144, "output": 8192},
}
MAX_BODY = 32 * 1024 * 1024
MCP_PORTS = {
    "/mcp": 8642,
    "/servers/context7/mcp": 8643,
    "/servers/github/mcp": 8643,
}
MCP_TOOLS = {
    "/mcp": {"search_web"},
    "/servers/context7/mcp": {"resolve-library-id", "query-docs"},
    "/servers/github/mcp": {"get_latest_release", "list_releases", "get_file_contents", "search_repositories"},
}
MCP_METHODS = {"initialize", "notifications/initialized", "ping", "tools/list", "tools/call"}
MCP_HEADERS = ("Accept", "Mcp-Session-Id", "Mcp-Protocol-Version", "Last-Event-ID")


class RouterConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=900)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Handler(BaseHTTPRequestHandler):
    # Closing the connection delimits streamed responses without copying the upstream
    # transfer encoding. http.client already decodes HTTP chunk framing.
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.forward()

    def do_DELETE(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def request_body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding is unsupported")
        sizes = self.headers.get_all("Content-Length", [])
        if len(sizes) > 1:
            raise ValueError("Duplicate Content-Length")
        size = int(sizes[0]) if sizes else 0
        if not 0 <= size <= MAX_BODY:
            raise ValueError("Request exceeds the body limit")
        return self.rfile.read(size) if size else None

    def forward(self):
        path = self.path
        method = self.command
        headers = {"Connection": "close"}
        is_mcp = path in MCP_PORTS and self.server.mcp
        if is_mcp:
            upstream = http.client.HTTPConnection("127.0.0.1", MCP_PORTS[path], timeout=120)
            headers.update({k: self.headers[k] for k in MCP_HEADERS if k in self.headers})
        else:
            upstream = RouterConnection(self.server.router)
            allowed = (
                method == "GET" and (
                    path in {"/health", "/models", "/v1/models", "/props"} or
                    (path.startswith("/props?model=") and
                     path[len("/props?model="):] in MODEL_MODELS)
                )
            ) or (method == "POST" and path == "/v1/chat/completions")
            if not allowed:
                self.send_error(403, "Endpoint outside the Pi profile")
                return

        try:
            body = self.request_body()
            if body is not None:
                headers["Content-Type"] = "application/json"
            if is_mcp and method == "POST":
                request = json.loads(body or b"null")
                if not isinstance(request, dict) or request.get("method") not in MCP_METHODS:
                    self.send_error(403, "MCP method outside the Pi profile")
                    return
                if request["method"] == "tools/call":
                    params = request.get("params")
                    if not isinstance(params, dict) or params.get("name") not in MCP_TOOLS[path]:
                        self.send_error(403, "MCP tool outside the Pi profile")
                        return
            if not is_mcp and method == "POST":
                request = json.loads(body or b"null")
                model = request.get("model") if isinstance(request, dict) else None
                if model not in MODEL_MODELS:
                    self.send_error(403, "Only the coding models are allowed")
                    return
                limit = request.pop("max_completion_tokens", request.get("max_tokens", MODEL_MODELS[model]["output"]))
                if type(limit) is not int:
                    raise ValueError("Invalid output limit")
                request["max_tokens"] = (
                    min(limit, MODEL_MODELS[model]["output"]) if limit > 0 else MODEL_MODELS[model]["output"]
                )
                # Keep inference single-sequence and prevent selection of another
                # slot or draft mode via backend-specific OpenAI extension fields.
                request["n"] = 1
                request.pop("id_slot", None)
                request.pop("n_predict", None)
                for key in list(request):
                    if key.startswith(("speculative", "spec_", "draft_")):
                        del request[key]
                body = json.dumps(request, allow_nan=False).encode()
        except (UnicodeError, ValueError, TypeError, RecursionError):
            self.send_error(400, "Invalid request body")
            return

        response_started = False
        try:
            upstream.request(method, path, body=body, headers=headers)
            response = upstream.getresponse()
            if not is_mcp and response.status == 200 and path in {"/models", "/v1/models"}:
                payload = json.loads(response.read())
                models = [model for model in payload.get("data", []) if model.get("id") in MODEL_MODELS]
                for model in models:
                    model["aliases"] = []
                    model["status"] = {
                        "value": model["status"]["value"],
                        "failed": model["status"].get("failed", False),
                        "args": ["--ctx-size", str(MODEL_MODELS[model["id"]]["context"])],
                    }
                body = json.dumps({"object": "list", "data": models}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                response_started = True
                self.wfile.write(body)
                return
            self.send_response(response.status)
            self.send_header("Connection", "close")
            forwarded = ("Content-Type", "Content-Length")
            if is_mcp:
                forwarded += ("Mcp-Session-Id", "Mcp-Protocol-Version")
            for key in forwarded:
                if key in response.headers:
                    self.send_header(key, response.headers[key])
            self.end_headers()
            response_started = True
            pending = b""
            is_chat_stream = path == "/v1/chat/completions" and response.headers.get(
                "Content-Type", ""
            ).startswith("text/event-stream")
            while chunk := response.read1(65536):
                self.wfile.write(chunk)
                if is_chat_stream:
                    pending += chunk
                    lines = pending.split(b"\n")
                    pending = lines.pop()
                    if any(line.rstrip(b"\r") == b"data: [DONE]" for line in lines):
                        break
                    # A model frame may be large. The sentinel itself fits in 14 bytes.
                    if len(pending) > 14:
                        pending = b" " + pending[-14:]
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, http.client.HTTPException, ValueError):
            if not response_started:
                self.send_error(502, "Pi upstream unavailable")
        finally:
            upstream.close()


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(30)
        return connection, address

    def handle_error(self, _request, _client_address):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("listen", type=Path)
    parser.add_argument("router", type=Path)
    parser.add_argument("--mcp", action="store_true")
    args = parser.parse_args()
    with Server(str(args.listen), Handler) as server:
        server.router = str(args.router)
        server.mcp = args.mcp
        server.serve_forever()
