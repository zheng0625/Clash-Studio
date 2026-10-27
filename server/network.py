"""Bounded public-IP lookup; never inherit another application's HTTP proxy."""
from __future__ import annotations

from concurrent.futures import Future
import ipaddress
import json
import threading
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException


class NetworkMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.Lock()
        self.cache = {}
        self.pending = {}

    @staticmethod
    def _json(client, url):
        with client.stream("GET", url) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 32768:
                    raise ValueError("Oversized lookup response")
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("Invalid lookup response")
            return value

    def lookup(self, route, refresh=False):
        runtime = self.runtime
        identity = runtime.egress_identity()
        with runtime.lock:
            active = dict(runtime.active or {})
            running = runtime.alive()
            session = runtime.process.pid if running else 0
            if route == "proxy" and (not running or not active):
                raise HTTPException(409, "请先启动本程序内核，再检测代理出口")
            proxy = f"http://127.0.0.1:{active['mixed_port']}" if route == "proxy" else None
            key = (route, identity)
        with self.lock:
            now = time.monotonic()
            cached = self.cache.get(key)
            ttl = 60 if cached and cached[1]["status"] != "unavailable" else 10
            if cached and not refresh and now - cached[0] < ttl:
                return {**cached[1], "cached": True}
            pending = self.pending.get(key)
            owner = pending is None
            if owner:
                pending = self.pending[key] = Future()
        if not owner:
            return dict(pending.result())
        try:
            result = self._lookup(route, runtime, identity, active, session, proxy)
            with self.lock:
                if len(self.cache) >= 8:
                    self.cache.clear()
                self.cache[key] = (time.monotonic(), result)
            pending.set_result(result)
            return dict(result)
        except BaseException as error:
            pending.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def _lookup(self, route, runtime, identity, active, session, proxy):
        started = time.monotonic()
        result = {"status": "unavailable", "ip": "", "country": "", "region": "", "city": "",
                  "isp": "", "asn": "", "family": "", "provider": "", "route": route,
                  "route_label": "本程序代理 · 按当前规则分流" if proxy else "系统路由 · 不使用应用代理设置",
                  "profile": active.get("title", "") if proxy else "",
                  "checked_at": datetime.now(timezone.utc).isoformat(), "cached": False,
                  "message": "检测服务暂不可达，无法据此判断整机是否断网"}
        try:
            with httpx.Client(proxy=proxy, trust_env=False, timeout=httpx.Timeout(6, connect=4),
                              follow_redirects=False, headers={"User-Agent": "ClashStudio/0.5.0"}) as client:
                try:
                    value = self._json(client, "https://ipwho.is/?lang=zh-CN")
                    if value.get("success") is not True:
                        raise ValueError("Lookup rejected")
                    ip = ipaddress.ip_address(value.get("ip", ""))
                    connection = value.get("connection") or {}
                    if not isinstance(connection, dict):
                        connection = {}
                    result.update(status="ok", ip=str(ip), family=f"IPv{ip.version}", provider="ipwho.is",
                                  country=str(value.get("country") or "")[:100],
                                  region=str(value.get("region") or "")[:100], city=str(value.get("city") or "")[:100],
                                  isp=str(connection.get("isp") or connection.get("org") or "")[:160],
                                  asn=str(connection.get("asn") or "")[:30], message="检测服务可达；位置为 IP 数据库近似归属地")
                except (httpx.HTTPError, ValueError, TypeError):
                    # A location-provider failure must not be reported as a general network outage.
                    client.timeout = httpx.Timeout(4, connect=3)
                    value = self._json(client, "https://api.ipify.org?format=json")
                    ip = ipaddress.ip_address(value.get("ip", ""))
                    result.update(status="partial", ip=str(ip), family=f"IPv{ip.version}", provider="ipify.org",
                                  message="公网 IP 已取得；归属地服务暂不可用")
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        result["checked_at"] = datetime.now(timezone.utc).isoformat()
        if runtime.egress_identity() != identity:
            raise HTTPException(409, '检测期间出口发生变化，请重新检测')
        result['egress_version'] = identity[-1]
        if proxy:
            with runtime.lock:
                if not runtime.alive() or runtime.process.pid != session or (runtime.active or {}).get("hash") != active.get("hash"):
                    raise HTTPException(409, "检测期间运行配置发生变化，请重新检测")
        return result

    def counters(self):
        return self.runtime.traffic()
