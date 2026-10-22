"""Bounded Mihomo HTTP delay probes; no policy selection is modified."""
from datetime import datetime, timezone
import threading
from urllib.parse import quote

from fastapi import HTTPException

ENDPOINTS = {"cloudflare": "https://cp.cloudflare.com/generate_204",
             "gstatic": "https://www.gstatic.com/generate_204"}


class DelayMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.slots = threading.BoundedSemaphore(4)

    def probe(self, name, endpoint, timeout_ms):
        if not self.slots.acquire(timeout=8):
            raise HTTPException(429, "已有四个节点正在测速，请稍后重试")
        try:
            with self.runtime.lock:
                if not self.runtime.alive():
                    raise HTTPException(409, "请先启动内核，再进行节点测速")
                session = self.runtime.process.pid
            proxies = self.runtime.request("GET", "/proxies").get("proxies", {})
            node = proxies.get(name)
            if node is None:
                raise HTTPException(404, "节点已不在运行配置中，请刷新代理页面")
            if node.get("all") is not None or node.get("type", "").lower() in ("direct", "reject", "rejectdrop", "pass", "dns"):
                raise HTTPException(422, "请选择实际代理节点测速")
            result = {"name": name, "endpoint": endpoint, "timeout_ms": timeout_ms,
                      "status": "unreachable", "delay_ms": None,
                      "checked_at": datetime.now(timezone.utc).isoformat()}
            try:
                value = self.runtime.request("GET", "/proxies/" + quote(name, safe="") + "/delay",
                                             params={"url": ENDPOINTS[endpoint], "timeout": timeout_ms},
                                             timeout=timeout_ms / 1000 + 2)
                delay = value.get("delay")
                if isinstance(delay, (float, int)) and not isinstance(delay, bool) and delay >= 0:
                    result.update(status="ok", delay_ms=round(delay))
            except HTTPException as error:
                if error.status_code == 409:
                    raise
            with self.runtime.lock:
                if not self.runtime.alive() or self.runtime.process.pid != session:
                    raise HTTPException(409, "测速期间内核已重启或停止，请重新测速")
            return result
        finally:
            self.slots.release()
