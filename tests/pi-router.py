#!/usr/bin/env python3
"""Offline regression checks for the Pi relay's public HTTP contract."""

import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import threading
from unittest import TestCase, main
from urllib.parse import urlsplit

spec = importlib.util.spec_from_file_location(
    "pi_router", Path(__file__).resolve().parents[1] / "libexec/pi-router.py"
)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)


class MockRouter(pi.Handler):
    def do_GET(self):
        body = json.dumps({"data": [
            {"id": model_id, "status": {"value": "loaded", "args": ["private-path"]}}
            for model_id in ("research-code", "story")
        ] + [
            {"id": "research", "status": {"value": "unloaded"}},
        ]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.server.post = json.loads(self.request_body())
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(b"data: [DONE]\n\n")


class OpenStreamRouter(MockRouter):
    def do_POST(self):
        self.request_body()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for data in (b"data: {\"sample\":1}\n\nda", b"ta: [DONE]", b"\n\n"):
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        # Stand in for a server that delays HTTP completion after ending SSE.
        time.sleep(3)


class RouterTest(TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.backend_path = f"{self.tmp}/backend.sock"
        self.path = f"{self.tmp}/relay.sock"
        self.backend = self.start(self.backend_path, MockRouter)
        self.relay = self.start(self.path, pi.Handler)
        self.relay.router = self.backend_path
        self.relay.mcp = False

    def start(self, path, handler):
        server = self.enterContext(pi.Server(path, handler))
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)
        return server

    def request(self, method, path, request=None):
        connection = pi.RouterConnection(self.path)
        self.addCleanup(connection.close)
        connection.request(method, path, body=json.dumps(request) if request is not None else None)
        response = connection.getresponse()
        return response.status, response.read()

    def test_catalog_keeps_allowed_models_with_own_context(self):
        status, raw = self.request("GET", "/models")
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["object"], "list")
        models = payload["data"]
        model_ids = [model["id"] for model in models]
        self.assertEqual(set(model_ids), {"research-code", "story"})
        self.assertTrue(set(model_ids) <= set(pi.MODEL_MODELS))
        for model in models:
            self.assertEqual(model["aliases"], [])
            self.assertEqual(model["status"]["args"],
                             ["--ctx-size", str(pi.MODEL_MODELS[model["id"]]["context"])])

    def test_models_run_at_the_full_256k_window(self):
        for model_id in ("research-code", "story"):
            with self.subTest(model=model_id):
                self.assertEqual(pi.MODEL_MODELS[model_id]["context"], 262144)
                self.assertEqual(pi.MODEL_MODELS[model_id]["output"], 8192)

    def test_inference_uses_one_slot_and_caps_output_per_model(self):
        for model_id, output in (("research-code", 8192), ("story", 8192)):
            with self.subTest(model=model_id):
                status, raw = self.request("POST", "/v1/chat/completions", {
                    "model": model_id, "max_tokens": 20000, "n": 3, "id_slot": 0,
                    "n_predict": 20000, "draft_max": 3, "stream": True,
                })
                self.assertEqual((status, raw), (200, b"data: [DONE]\n\n"))
                self.assertEqual(self.backend.post, {
                    "model": model_id, "max_tokens": output, "n": 1, "stream": True,
                })

    def test_sse_done_finishes_response_before_upstream_disconnects(self):
        self.relay.router = f"{self.tmp}/open-stream.sock"
        self.start(self.relay.router, OpenStreamRouter)
        start = time.monotonic()
        status, body = self.request("POST", "/v1/chat/completions", {"model": pi.MODEL, "stream": True})
        self.assertEqual(status, 200)
        self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
        self.assertLess(time.monotonic() - start, 2)

    def test_disallowed_model_and_management_routes(self):
        for method, path, payload in (
            ("GET", "/props?model=research", None),
            ("POST", "/models/unload", {"model": pi.MODEL}),
            ("POST", "/models/download", {"model": pi.MODEL}),
            ("POST", "/v1/chat/completions", {"model": "research"}),
            ("POST", "/mcp", {"method": "tools/list"}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, payload)[0], 403)
        self.assertFalse(hasattr(self.backend, "post"))

    def test_mcp_rejects_calls_outside_the_approved_scope(self):
        self.relay.mcp = True
        for endpoint, tool in (("/mcp", "deep_research"), ("/mcp", "read_url"),
                               ("/servers/github/mcp", "push_files")):
            self.assertEqual(self.request("POST", endpoint, {
                "method": "tools/call", "params": {"name": tool},
            })[0], 403)

    def test_mcp_exposure_matches_the_relay_allowlist(self):
        config = Path(__file__).resolve().parents[1] / "config/pi.json.in"
        servers = json.loads(config.read_text())["mcpServers"]
        tools_by_endpoint = {}
        for server in servers.values():
            endpoint = urlsplit(server["url"])
            self.assertEqual(endpoint.hostname, "127.0.0.1")
            self.assertEqual(endpoint.port, pi.MCP_PORTS[endpoint.path])
            self.assertEqual(server["exposure"], "hidden")
            tools_by_endpoint[endpoint.path] = {
                name for name, exposure in server["toolExposure"].items() if exposure == "codemode"
            }
        self.assertEqual(tools_by_endpoint, pi.MCP_TOOLS)


if __name__ == "__main__":
    main()
