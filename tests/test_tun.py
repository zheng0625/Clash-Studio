from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.api import build_app
from server.runtime import Runtime
import server.runtime as runtime_module


def test_tun_compile_is_explicit_and_dns_is_completed(tmp_path):
    runtime = Runtime(tmp_path)
    composed = {"config": {"proxies": [], "tun": {"enable": True}, "listeners": [{"port": 7899}], "rules": ["MATCH,DIRECT"]}}
    plain = runtime.prepare(composed, 17890)
    from app.engine import parse_config
    assert parse_config(plain)["tun"] == {"enable": False}
    assert "listeners" not in parse_config(plain)
    configured = parse_config(runtime.prepare(composed, 17890, True, "gvisor"))
    assert configured["tun"]["enable"]
    assert configured["tun"]["device"] == "ClashStudio"
    assert configured["tun"]["strict-route"]
    assert configured["tun"]["stack"] == "gvisor"
    assert configured["dns"]["enable"]
    assert configured["dns"]["nameserver"]


def test_no_route_change_without_privilege_or_with_conflicting_core(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    if not runtime.platform.info['capabilities']['tun']:
        with pytest.raises(HTTPException) as error:
            runtime.apply({"config": {}, "errors": []}, {}, 17890, True)
        assert error.value.status_code == 501
        assert runtime.process is None
        return
    monkeypatch.setattr(runtime_module, "other_cores", lambda own_pid: ["verge-mihomo.exe (PID 1)"])
    with pytest.raises(HTTPException) as error:
        runtime.apply({"config": {}, "errors": []}, {}, 17890, True)
    assert "其他代理内核" in error.value.detail
    assert runtime.process is None


def test_desktop_backend_nonce_is_required_for_read_and_write(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASH_STUDIO_DESKTOP_TOKEN", "test-desktop-nonce")
    with TestClient(build_app(tmp_path)) as client:
        assert client.get("/api/client/workspace").status_code == 403
        headers = {"X-Clash-Studio": "1", "X-Clash-Desktop-Token": "test-desktop-nonce"}
        response = client.get("/api/client/workspace", headers=headers)
        assert response.status_code == 200
        assert client.put("/api/client/workspace", headers={"X-Clash-Studio": "1"}, json=response.json()).status_code == 403
        assert client.put("/api/client/workspace", headers=headers, json=response.json()).status_code == 200
