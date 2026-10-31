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
                  "isp": "", "asn": "", "family": "", "provider": "ippure.com", "route": route,
                  "country_code": "", "is_residential": None, "is_broadcast": None,
                  "route_label": "本程序代理 · 按当前规则分流" if proxy else "系统路由 · 不使用应用代理设置",
                  "profile": active.get("title", "") if proxy else "",
                  "checked_at": datetime.now(timezone.utc).isoformat(), "cached": False,
                  "message": "IPPure 查询暂不可用，请稍后重试"}
        try:
            with httpx.Client(proxy=proxy, trust_env=False, timeout=httpx.Timeout(8, connect=4),
                              follow_redirects=True, headers={"User-Agent": "ClashStudio/1.3.0", "Accept": "application/json"}) as client:
                value = self._json(client, "https://my.ippure.com/v1/info")
                ip = ipaddress.ip_address(value.get("ip", ""))
                country, region, city = (str(value.get(key) or "")[:100] for key in ("country", "region", "city"))
                # Missing values remain unknown. Never coerce null or strings into
                # a residential/data-center or native/broadcast classification.
                residential = value.get("isResidential")
                broadcast = value.get("isBroadcast")
                residential = residential if isinstance(residential, bool) else None
                broadcast = broadcast if isinstance(broadcast, bool) else None
                complete = bool(country or region or city) and residential is not None and broadcast is not None
                result.update(status="ok" if complete else "partial", ip=str(ip), family=f"IPv{ip.version}",
                              country=country, region=region, city=city,
                              country_code=str(value.get("countryCode") or "")[:2],
                              isp=str(value.get("asOrganization") or "")[:160], asn=str(value.get("asn") or "")[:30],
                              is_residential=residential, is_broadcast=broadcast,
                              message="" if complete else "IPPure 未返回部分地址或属性信息")
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
