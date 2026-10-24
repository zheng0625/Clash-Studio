import os
import shutil
from pathlib import Path
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from fastapi.testclient import TestClient

from server.api import build_app
from server.platforms import core_binary

HEADERS = {"X-Clash-Studio": "1"}
CONFIG = """
proxies:
  - {name: TestProxy, type: ss, server: 127.0.0.1, port: 1, cipher: aes-128-gcm, password: test-only}
proxy-groups:
  - {name: Work, type: select, proxies: [DIRECT, REJECT]}
  - {name: Locked, type: select, proxies: [TestProxy]}
rules:
  - MATCH,Work
"""


def test_real_core_lifecycle_dispatch_and_revision(tmp_path):
    source = core_binary(Path(__file__).resolve().parents[1])
    (tmp_path / "bin").mkdir()
    shutil.copy2(source, tmp_path / "bin" / source.name)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        proxy_port = probe.getsockname()[1]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"alpha-local-egress-ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    app = build_app(tmp_path)
    before_proxy = app.state.runtime.proxy.status()
    try:
        with TestClient(app) as client:
            assert client.get("/api/client/info").json()["app"] == "clash-studio-alpha"
            assert client.put("/api/client/workspace", json={}).status_code == 403
            imported = client.post("/api/subscriptions", headers=HEADERS,
                json={"title": "local-core-test", "source_type": "file", "yaml": CONFIG})
            assert imported.status_code == 201, imported.text
            profile = imported.json()
            workspace = client.get("/api/client/workspace").json()
            workspace["modules"] = [{"id": "blocked", "name": "拒绝测试目标", "target": "REJECT", "strict": True,
                                      "matches": [{"kind": "IP-CIDR", "value": "127.0.0.2/32"}]}]
            workspace["plans"][profile["id"]] = {"module_ids": ["blocked"], "default_target": "Work"}
            saved = client.put("/api/client/workspace", json=workspace, headers=HEADERS)
            assert saved.status_code == 200, saved.text
            preview = client.get(f"/api/client/preview/{profile['id']}").json()
            assert not preview["errors"]
            body = {"profile_id": profile["id"], "profile_revision": profile["revision"],
                    "workspace_revision": preview["workspace_revision"], "mixed_port": proxy_port, "proxy_mode": "manual"}
            started = client.post("/api/client/runtime/apply", json=body, headers=HEADERS)
            assert started.status_code == 200, started.text
            assert started.json()["running"]
            assert not started.json()["proxy"]["owned"]
            proxies = client.get("/api/client/runtime/proxies").json()["proxies"]
            assert proxies["Work"]["now"] == "DIRECT"
            with httpx.Client(proxy=f"http://127.0.0.1:{proxy_port}", trust_env=False, timeout=4) as traffic:
                allowed = traffic.get(f"http://127.0.0.1:{origin.server_port}/")
                assert allowed.text == "alpha-local-egress-ok"
                blocked = traffic.get(f"http://127.0.0.2:{origin.server_port}/")
                assert blocked.status_code >= 400
                switch = client.put("/api/client/runtime/proxies/Work", json={"name": "REJECT"}, headers=HEADERS)
                assert switch.status_code == 200, switch.text
                rejected = traffic.get(f"http://127.0.0.1:{origin.server_port}/")
                assert rejected.status_code >= 400
            # Stale previews must not overwrite the currently running config.
            body["workspace_revision"] -= 1
            assert client.post("/api/client/runtime/apply", json=body, headers=HEADERS).status_code == 409
            assert client.get("/api/client/runtime").json()["running"]
            assert client.get("/api/client/runtime/connections").status_code == 200
            stopped = client.post("/api/client/runtime/stop", headers=HEADERS, json={})
            assert stopped.status_code == 200 and not stopped.json()["running"]
            assert app.state.runtime.proxy.status() == before_proxy
    finally:
        app.state.runtime.stop()
        origin.shutdown()
        origin.server_close()
