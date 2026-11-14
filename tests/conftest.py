"""Fake local OCR API for the tests. No network, no key, never the production API.
Run (venv with `pip install -e ".[test]"`): python -m pytest integrations/langchain -p no:cacheprovider"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from ocr_software import client as client_module

PDF = b"%PDF-1.4 fake"


class Fake(BaseHTTPRequestHandler):
    """Every submit is job j<N>; state["result"] replaces the result text; GET /v1/catalog lists cheap@1 and dear@1. fail_submits: that many 503 first. unread: the jobs end with a failed page."""
    log, queries, state = [], [], {}

    def _send(self, status, payload, headers=None):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        path = self.path.split("?")[0]
        Fake.log.append((self.command, path, self.headers.get("Authorization"), self.headers.get("Idempotency-Key")))
        Fake.queries.append(self.path.partition("?")[2])
        if self.command == "POST":
            if Fake.state["fail_submits"] > 0:
                Fake.state["fail_submits"] -= 1
                return self._send(503, {"error": {"code": "busy", "message": "busy"}}, {"Retry-After": "0"})
            Fake.state["jobs"] += 1
            return self._send(202, {"job_id": "j%d" % Fake.state["jobs"], "state": "running"})
        if path == "/v1/catalog":
            return self._send(200, {"pipelines": [{"pipeline": "cheap@1", "factor": 1}, {"pipeline": "dear@1", "factor": 4}]})
        if path.endswith("/result"):
            return self._send(200, Fake.state.get("result") or ("text of " + path.split("/")[3]).encode())
        failed = 1 if Fake.state["unread"] else 0
        self._send(200, {"job_id": path.rsplit("/", 1)[1], "state": "done", "pages_failed": failed, "pages_not_run": 0})

    do_GET = do_POST = _handle

    def log_message(self, *args):
        pass


@pytest.fixture
def fake(monkeypatch):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=lambda: httpd.serve_forever(0.02), daemon=True).start()
    Fake.log, Fake.queries, Fake.state = [], [], {"jobs": 0, "fail_submits": 0, "unread": False}
    for name in ("OCR_KEY", "OCR_BASE_URL", "OCR_SOFTWARE_BASE_URL", "OCR_ALLOWED_DIR", "OCR_SOFTWARE_ALLOWED_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OCR_SOFTWARE_API_KEY", "ocr_testkey")
    monkeypatch.setattr(client_module, "BACKOFF_BASE_S", 0)
    Fake.url = "http://127.0.0.1:%d" % httpd.server_address[1]
    yield Fake
    httpd.shutdown()


@pytest.fixture
def docs(tmp_path):
    paths = []
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        p = tmp_path / name
        p.write_bytes(PDF)
        paths.append(str(p))
    return paths
