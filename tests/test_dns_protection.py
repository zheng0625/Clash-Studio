import copy
import json
from pathlib import Path
import socket
import socketserver
import subprocess
import threading
import time
from types import SimpleNamespace
from urllib.request import urlopen

import pytest
from app.engine import parse_config
from server.runtime import Runtime
from server.platforms import core_binary
from server.settings import ClientSettings, SettingsStore
from conftest import free_mixed_port


def prepared(settings, source, tun=False, platform="windows"):
    runtime = SimpleNamespace(settings=SimpleNamespace(load=lambda: settings),
        routing_mode="rule", controller_port=0, secret="test-only",
        platform=SimpleNamespace(info={"os": platform}))
    return parse_config(Runtime.prepare(runtime, {"config": source}, 0, tun=tun))


def unsafe_dns(port=5353):
    return {"enable": True, "enhanced-mode": "redir-host",
        "nameserver": [f"udp://127.0.0.1:{port}"],
        "nameserver-policy": {"+.example": [f"udp://127.0.0.1:{port}#DIRECT"]},
        "fallback": [f"udp://127.0.0.1:{port}"], "fallback-filter": {"geoip": False},
        "proxy-server-nameserver-policy": {"+.example": ["system"]},
        "proxy-server-nameserver": [], "default-nameserver": [], "direct-nameserver": [],
        "prefer-h3": True, "direct-nameserver-follow-policy": True}


@pytest.mark.parametrize("override", [False, True])
def test_protection_cleans_policies_without_mutating_profile(override):
    source = {"dns": unsafe_dns(), "proxy-groups": [{"name": "ClashStudio-DNS", "type": "select", "proxies": ["DIRECT"]}]}
    original = copy.deepcopy(source)
    settings = ClientSettings(dns_leak_prevention=True, dns_override={"enabled": override})
    config = prepared(settings, source)
    assert source == original
    dns = config["dns"]
    assert dns["enable"] and dns["respect-rules"]
    for key in ["nameserver-policy", "fallback", "fallback-filter", "prefer-h3", "proxy-server-nameserver-policy"]:
        assert key not in dns
    group = config["proxy-groups"][-1]
    assert group["name"] == "ClashStudio-DNS-protected"
    assert group["empty-fallback"] == "REJECT"
    assert group["include-all"]
    assert {"Direct", "Compatible", "Pass", "PassRule", "Rematch", "Dns"} <= set(group["exclude-type"].split("|"))
    assert all(v.endswith("#" + group["name"]) for v in dns["nameserver"])
    assert all(dns[k] for k in ["default-nameserver", "proxy-server-nameserver", "direct-nameserver"])
    assert dns["direct-nameserver-follow-policy"] is False


def test_disable_restores_profile_and_settings_survive_restart(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    old = store.load().model_dump(); old.pop("dns_leak_prevention"); old.pop("tun_strict_route")
    assert ClientSettings(**old).dns_leak_prevention is False
    assert ClientSettings(**old).tun_strict_route is True
    source = {"dns": unsafe_dns(), "proxies": []}
    for enabled in [True, False]:
        store.save(ClientSettings(dns_leak_prevention=enabled, tun_strict_route=False))
        settings = SettingsStore(store.path).load()
        assert settings.dns_leak_prevention == enabled
        assert settings.tun_strict_route is False
        config = prepared(settings, source)
        if not enabled:
            assert "proxy-groups" not in config
            assert all(config["dns"][key] == value for key, value in source["dns"].items())


@pytest.mark.parametrize("platform", ["windows", "linux"])
@pytest.mark.parametrize("strict", [False, True])
def test_strict_route_maps_to_tun(platform, strict):
    settings = ClientSettings(tun_strict_route=strict, dns_leak_prevention=True)
    assert prepared(settings, {}, tun=True, platform=platform)["tun"]["strict-route"] == strict
    assert prepared(settings, {}, tun=False, platform=platform)["tun"] == {"enable": False}


class ProxyHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.requests.append(self.rfile.readline().decode("ascii", errors="replace").strip())
        self.wfile.write(b"HTTP/1.1 502 Test-only proxy\r\nContent-Length: 0\r\n\r\n")


@pytest.mark.parametrize("mode,provider", [("rule", False), ("global", False), ("direct", False), ("rule", True)])
def test_real_core_uses_proxy_and_never_old_plaintext_policy(tmp_path, mode, provider):
    binary = core_binary(Path(__file__).resolve().parents[1])
    if not binary.exists():
        pytest.skip("bundled platform core unavailable")
    # No host proxy/TUN/DNS changes. The proxy refuses CONNECT, so no external
    # connection can be made even though the protected DoH URLs are genuine.
    proxy = socketserver.ThreadingTCPServer(("127.0.0.1", 0), ProxyHandler)
    proxy.daemon_threads = True
    proxy.requests = []
    thread = threading.Thread(target=proxy.serve_forever, daemon=True); thread.start()
    plaintext = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    plaintext.bind(("127.0.0.1", 0)); plaintext.settimeout(.1)
    controller, dns_port = free_mixed_port(), free_mixed_port()
    node = {"name": "TestProxy", "type": "http", "server": "127.0.0.1", "port": proxy.server_address[1]}
    source = {"dns": unsafe_dns(plaintext.getsockname()[1]), "rules": ["MATCH,DIRECT"]}
    if provider:
        source["proxy-providers"] = {"Inline": {"type": "inline", "payload": [node, {"name": "UnsafeDirect", "type": "direct"}]}}
    else:
        source["proxies"] = [node, {"name": "UnsafeDirect", "type": "direct"}]
    config = prepared(ClientSettings(dns_leak_prevention=True), source)
    config["mode"] = mode
    config["external-controller"] = f"127.0.0.1:{controller}"; config["secret"] = ""
    config["dns"]["listen"] = f"127.0.0.1:{dns_port}"
    name = config["proxy-groups"][-1]["name"]
    candidate = tmp_path / "config.json"; candidate.write_text(json.dumps(config), encoding="utf-8")
    with (tmp_path / "core.log").open("wb") as log:
        process = subprocess.Popen([str(binary), "-d", str(tmp_path), "-f", str(candidate)], stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 8
            while True:
                assert process.poll() is None, (tmp_path / "core.log").read_text(encoding="utf-8")
                try:
                    with urlopen(f"http://127.0.0.1:{controller}/proxies/{name}", timeout=.3) as response:
                        group = json.load(response)
                    break
                except OSError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(.05)
            assert group["all"] == ["TestProxy"]
            query = b'\x47\x11\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06review\x07example\x00\x00\x01\x00\x01'
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(.5); client.sendto(query, ("127.0.0.1", dns_port))
                # Wait until the query has reached the proxy (not a sleeping heuristic).
                deadline = time.monotonic() + 5
                while not any("1.1.1.1:443" in v or "8.8.8.8:443" in v for v in proxy.requests):
                    assert time.monotonic() < deadline, (tmp_path / "core.log").read_text(encoding="utf-8")
                    time.sleep(.02)
                try:
                    reply = client.recv(4096)
                    assert int.from_bytes(reply[6:8], "big") == 0  # no successful answer from a failed proxy
                except socket.timeout:
                    pass
            with pytest.raises(socket.timeout): plaintext.recvfrom(4096)
        finally:
            process.terminate(); process.wait(timeout=5)
            proxy.shutdown(); proxy.server_close(); plaintext.close()


def test_real_core_rejects_empty_group_instead_of_compatible(tmp_path):
    binary = core_binary(Path(__file__).resolve().parents[1])
    if not binary.exists(): pytest.skip("bundled platform core unavailable")
    config = prepared(ClientSettings(dns_leak_prevention=True), {"dns": unsafe_dns(), "rules": ["MATCH,REJECT"]})
    controller = free_mixed_port()
    config["external-controller"] = f"127.0.0.1:{controller}"
    config["secret"] = ""
    path = tmp_path / "config.json"; path.write_text(json.dumps(config), encoding="utf-8")
    result = subprocess.run([str(binary), "-t", "-d", str(tmp_path), "-f", str(path)], capture_output=True, timeout=8)
    assert result.returncode == 0, result.stdout.decode("utf-8", errors="replace")
    with (tmp_path / "empty-group.log").open("wb") as log:
        process = subprocess.Popen([str(binary), "-d", str(tmp_path), "-f", str(path)], stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 5
            while True:
                assert process.poll() is None
                try:
                    with urlopen(f"http://127.0.0.1:{controller}/proxies/ClashStudio-DNS", timeout=.3) as response:
                        group = json.load(response)
                    break
                except OSError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(.05)
            assert group["all"] == ["REJECT"]
            assert group["now"] == "REJECT"
        finally:
            process.terminate(); process.wait(timeout=5)
