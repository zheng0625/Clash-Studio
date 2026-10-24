"""Elevated, real Windows TUN acceptance check. No user subscription or proxy edits."""
from __future__ import annotations

import ctypes
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import threading
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
HOME = ARTIFACTS / ("tun-live-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
HOME.mkdir(exist_ok=False)
RESULT = ARTIFACTS / "tun-check-latest.json"
report = {"started_at": datetime.now().astimezone().isoformat(), "folder": str(HOME),
          "state": "starting", "checks": [], "scope": "Windows TUN IPv4, DIRECT test traffic only"}


def save():
    temp = RESULT.with_suffix(".tmp")
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    (HOME / "report.json").write_text(serialized, encoding="utf-8")
    temp.write_text(serialized, encoding="utf-8")
    temp.replace(RESULT)


def record(name, passed, **details):
    report["checks"].append({"name": name, "passed": bool(passed), **details})
    report["state"] = name
    save()
    if not passed:
        raise RuntimeError(name)


def windows_snapshot():
    command = r"""[PSCustomObject]@{
      Adapters=@(Get-NetAdapter -IncludeHidden | Where-Object { $_.Name -eq 'ClashStudio' } | Select-Object Name,ifIndex,Status);
      Defaults=@(Get-NetRoute -ErrorAction SilentlyContinue | Where-Object { $_.DestinationPrefix -in @('0.0.0.0/0','::/0') } | Select-Object DestinationPrefix,InterfaceIndex,NextHop,RouteMetric);
      Routes=@(Get-NetRoute -ErrorAction SilentlyContinue | Select-Object DestinationPrefix,InterfaceIndex,NextHop)
    } | ConvertTo-Json -Depth 4 -Compress"""
    flags = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, timeout=15, creationflags=flags)
    if result.returncode:
        raise RuntimeError("Windows route inventory failed")
    return json.loads(result.stdout.decode("utf-8-sig"))


def fake_ip(domain):
    transaction = secrets.randbelow(65536)
    name = b"".join(bytes([len(label)]) + label.encode("ascii") for label in domain.split(".")) + b"\0"
    packet = struct.pack("!6H", transaction, 0x100, 1, 0, 0, 0) + name + struct.pack("!2H", 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dns:
        dns.settimeout(5)
        dns.sendto(packet, ("1.1.1.1", 53))
        answer = dns.recv(4096)
    if len(answer) < 12 or struct.unpack("!H", answer[:2])[0] != transaction:
        raise RuntimeError("Invalid DNS reply")

    def skip_name(offset):
        while answer[offset]:
            if answer[offset] & 0xc0 == 0xc0:
                return offset + 2
            offset += answer[offset] + 1
        return offset + 1

    _, flags, questions, count, _, _ = struct.unpack("!6H", answer[:12])
    if flags & 15:
        raise RuntimeError("DNS returned an error")
    offset = 12
    for _ in range(questions):
        offset = skip_name(offset) + 4
    for _ in range(count):
        offset = skip_name(offset)
        kind, family, _, length = struct.unpack("!HHIH", answer[offset:offset + 10])
        offset += 10
        if kind == 1 and family == 1 and length == 4:
            return socket.inet_ntoa(answer[offset:offset + length])
        offset += length
    raise RuntimeError("DNS returned no IPv4 answer")


save()
runtime = None
baseline = None
proxy_before = None
try:
    import httpx
    from server.runtime import Runtime
    from server.windows import is_admin, other_cores
    from server.network import NetworkMonitor

    record("administrator", is_admin())
    conflicts = other_cores()
    record("no_conflicting_core", not conflicts, conflicts=conflicts)
    (HOME / "bin").mkdir()
    for filename in ["mihomo-windows-amd64-compatible.exe", "wintun.dll"]:
        os.link(ROOT / "bin" / filename, HOME / "bin" / filename)
    runtime = Runtime(HOME)
    proxy_before = runtime.proxy.status()
    baseline = windows_snapshot()
    # Never delete or reuse another instance's existing virtual adapter.
    record("no_existing_studio_tun", not any(a["Status"] == "Up" for a in baseline["Adapters"]))
    with httpx.Client(trust_env=False, timeout=12) as client:
        response = client.get("http://www.msftconnecttest.com/connecttest.txt")
        record("baseline_internet", response.status_code == 200 and "Microsoft Connect Test" in response.text)

    def watchdog():
        report["watchdog"] = "time limit reached"
        save()
        if runtime and runtime.alive():
            runtime.process.terminate()
        os._exit(124)

    watchdog_timer = threading.Timer(180, watchdog)
    watchdog_timer.daemon = True
    watchdog_timer.start()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = {"proxies": [], "proxy-groups": [{"name": "TUN-Check", "type": "select", "proxies": ["DIRECT", "REJECT"]}],
              "rules": ["DOMAIN-SUFFIX,example.com,REJECT", "MATCH,TUN-Check"], "ipv6": False,
              "dns": {"default-nameserver": ["223.5.5.5", "1.1.1.1"],
                      "nameserver": ["https://dns.alidns.com/dns-query", "https://1.1.1.1/dns-query"]}}
    composed = {"config": config, "errors": [], "workspace_revision": 1}
    row = {"id": "tun-acceptance", "title": "TUN isolated acceptance", "revision": 1, "enabled": True}
    report["state"] = "enabling_tun"
    save()
    status = runtime.apply(composed, row, port, tun=True, tun_stack="mixed")
    record("core_confirms_tun", status["running"] and status["tun"]["enabled"])
    active = windows_snapshot()
    indices = {a["ifIndex"] for a in active["Adapters"] if a["Status"] == "Up"}
    record("virtual_adapter_and_routes", bool(indices) and any(r["InterfaceIndex"] in indices for r in active["Routes"]),
           adapters=active["Adapters"], route_count=sum(r["InterfaceIndex"] in indices for r in active["Routes"]))
    address = fake_ip("example.org")
    record("dns_hijack_fake_ip", ipaddress.ip_address(address) in ipaddress.ip_network("198.18.0.0/16"),
           response_kind="fake" if ipaddress.ip_address(address) in ipaddress.ip_network("198.18.0.0/16") else "real")
    monitor = NetworkMonitor(runtime)
    before = monitor.counters()
    with httpx.Client(trust_env=False, timeout=12) as client:
        response = client.get(f"http://{address}/", headers={"Host": "example.org"})
        record("transparent_tun_http", response.status_code == 200 and "Example Domain" in response.text)
        # Hold an ordinary TCP flow open so the short HTTP response cannot
        # disappear from the connection list before the observation.
        with socket.create_connection((address, 80), timeout=5) as held:
            held.sendall(b"GET / HTTP/1.1\r\nHost: example.org\r\n")
            time.sleep(.3)
            connections = runtime.request("GET", "/connections").get("connections", [])
        observed = [c for c in connections if c.get("metadata", {}).get("type", "").lower() == "tun"]
        record("tun_connection_observed", bool(observed), count=len(observed),
               chains=[c.get("chains", []) for c in observed], rules=[c.get("rule") for c in observed])
        normal = client.get("http://www.msftconnecttest.com/connecttest.txt")
        record("system_resolver_tun_http", normal.status_code == 200 and "Microsoft Connect Test" in normal.text)
    blocked_ip = fake_ip("example.com")
    blocked = False
    try:
        with httpx.Client(trust_env=False, timeout=5) as client:
            response = client.get(f"http://{blocked_ip}/", headers={"Host": "example.com"})
            blocked = response.status_code >= 400
    except httpx.HTTPError:
        blocked = True
    time.sleep(.3)
    core_log = (HOME / "data" / "runtime" / "core.log").read_text(encoding="utf-8", errors="replace")
    record("domain_reject", blocked and any("example.com" in line and "REJECT" in line for line in core_log.splitlines()))
    runtime.request("PUT", "/proxies/TUN-Check", json={"name": "REJECT"})
    rejected = False
    try:
        with httpx.Client(trust_env=False, timeout=5) as client:
            rejected = client.get(f"http://{address}/", headers={"Host": "example.org"}).status_code >= 400
    except httpx.HTTPError:
        rejected = True
    record("selector_reject", rejected)
    runtime.request("PUT", "/proxies/TUN-Check", json={"name": "DIRECT"})
    with httpx.Client(trust_env=False, timeout=12) as client:
        response = client.get(f"http://{address}/", headers={"Host": "example.org"})
        record("selector_direct_recovery", response.status_code == 200 and "Example Domain" in response.text)
    lookup = monitor.lookup("proxy", refresh=True)
    record("proxy_ip_lookup", lookup["status"] in ("ok", "partial"), status=lookup["status"],
           location_available=bool(lookup["country"]), family=lookup["family"])
    after = monitor.counters()
    record("traffic_counters_increase", after["download"] > before["download"] and after["upload"] > before["upload"],
           download_bytes=after["download"] - before["download"], upload_bytes=after["upload"] - before["upload"])
    status = runtime.change_tun(False, "mixed")
    record("tun_disable_acknowledged", not status["tun"]["enabled"] and status["running"])
    runtime.stop()
    time.sleep(1)
    restored = windows_snapshot()
    record("tun_routes_removed", not any(r["InterfaceIndex"] in indices for r in restored["Routes"]))
    def defaults(snapshot):
        return sorted(json.dumps(r, sort_keys=True) for r in snapshot["Defaults"])
    record("default_routes_restored", defaults(restored) == defaults(baseline))
    record("system_proxy_unchanged", runtime.proxy.status() == proxy_before)
    with httpx.Client(trust_env=False, timeout=12) as client:
        response = client.get("http://www.msftconnecttest.com/connecttest.txt")
        record("internet_after_stop", response.status_code == 200 and "Microsoft Connect Test" in response.text)
    report["state"] = "passed"
    watchdog_timer.cancel()
except BaseException as error:
    report["state"] = "failed"
    report["error"] = {"type": type(error).__name__, "detail": str(getattr(error, "detail", ""))[:500]}
finally:
    if runtime:
        try:
            runtime.stop()
            report["cleanup"] = {"core_stopped": not runtime.alive(), "proxy_unchanged": runtime.proxy.status() == proxy_before}
        except Exception as error:
            report["cleanup"] = {"error_type": type(error).__name__}
    report["finished_at"] = datetime.now().astimezone().isoformat()
    save()
