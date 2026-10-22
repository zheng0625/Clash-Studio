"""Optional LAN listener serving tokenised subscriptions only.

The management app remains bound to loopback. Forwarded headers are never used
to decide a LAN client's address, and only RFC1918 IPv4 peers are accepted.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LAN_RANGES = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
DEFAULT_PORT = 8767


def is_lan_ipv4(value: str, loopback=False):
    try:
        address = ipaddress.ip_address(value)
        return address.version == 4 and (any(address in net for net in LAN_RANGES) or (loopback and address.is_loopback))
    except ValueError:
        return False


def lan_addresses():
    """Detect local IPv4 addresses without sending traffic to external services."""
    addresses, preferred = set(), ""
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            if is_lan_ipv4(entry[4][0]):
                addresses.add(entry[4][0])
    except OSError:
        pass
    try:
        # UDP connect selects a local route; no datagram is sent.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            preferred = probe.getsockname()[0]
            if is_lan_ipv4(preferred):
                addresses.add(preferred)
    except OSError:
        pass
    return [{"address": address, "preferred": address == preferred} for address in
            sorted(addresses, key=lambda address: (address != preferred, int(ipaddress.ip_address(address))))]


def build_lan_app(subscription_handler):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        peer = request.client.host if request.client else ""
        if not is_lan_ipv4(peer, loopback=True):
            return JSONResponse({"detail": "仅允许局域网设备访问"}, status_code=403)
        try:
            host = request.url.hostname or ""
        except ValueError:
            host = ""
        allowed = {"127.0.0.1", "localhost"} | {item["address"] for item in lan_addresses()}
        if host not in allowed:
            return JSONResponse({"detail": "无效的局域网服务地址"}, status_code=400)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.add_api_route("/sub/{token}", subscription_handler, methods=["GET", "HEAD"])
    return app


class SubscriptionServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # The management server owns process signals; a nested server must not
        # replace its Ctrl+C handlers or keep the main process alive on shutdown.
        yield


class LanController:
    def __init__(self, directory: Path, app: FastAPI):
        self.path = directory / "network.json"
        self.app = app
        self.config = {"enabled": False, "port": DEFAULT_PORT, "preferred_host": ""}
        self.error = ""
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(saved.get("enabled"), bool) or not isinstance(saved.get("port"), int) or isinstance(saved.get("port"), bool) or not 1024 <= saved["port"] <= 65535:
                    raise ValueError()
                preferred = saved.get("preferred_host", "")
                if not isinstance(preferred, str) or (preferred and not is_lan_ipv4(preferred)):
                    raise ValueError()
                self.config = {"enabled": saved["enabled"], "port": saved["port"], "preferred_host": preferred}
            except (ValueError, TypeError, OSError):
                self.error = "局域网设置文件无效，已使用默认关闭状态"
        self.server = None
        self.task = None
        self.listener = None
        self.lock = asyncio.Lock()

    def status(self):
        addresses = lan_addresses()
        selected = next((item["address"] for item in addresses if item["address"] == self.config["preferred_host"]), "")
        selected = selected or (addresses[0]["address"] if addresses else "")
        running = bool(self.server and self.server.started and self.task and not self.task.done())
        return {"enabled": self.config["enabled"], "port": self.config["port"],
                "selected_host": selected, "addresses": addresses, "running": running,
                "base_url": f"http://{selected}:{self.config['port']}" if running and selected else "",
                "error": self.error}

    def persist(self, config):
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    async def _start(self, port):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("0.0.0.0", port))
            listener.listen(128)
            listener.setblocking(False)
        except OSError:
            listener.close()
            raise ValueError("局域网端口无法监听，请检查端口是否被占用，或选择其他端口") from None
        server = SubscriptionServer(uvicorn.Config(self.app, host="0.0.0.0", port=port,
                access_log=False, proxy_headers=False, server_header=False, lifespan="off", log_level="warning"))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(200):
                if server.started and not task.done():
                    return server, task, listener
                if task.done():
                    break
                await asyncio.sleep(0.01)
            raise ValueError("局域网订阅服务启动失败")
        except BaseException:
            server.should_exit = True
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            listener.close()
            raise

    @staticmethod
    async def _stop(server, task, listener):
        if server:
            server.should_exit = True
        if task:
            try:
                await asyncio.wait_for(asyncio.shield(task), 3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if listener:
            listener.close()

    async def start(self):
        if self.config["enabled"]:
            try:
                self.server, self.task, self.listener = await self._start(self.config["port"])
            except ValueError as exc:
                self.error = str(exc)

    async def close(self):
        async with self.lock:
            await self._stop(self.server, self.task, self.listener)
            self.server = self.task = self.listener = None

    async def update(self, enabled: bool, port: int, preferred_host: str, management_port: int):
        async with self.lock:
            if enabled and port == management_port:
                raise ValueError("局域网订阅端口不能与本机管理端口相同")
            if enabled and preferred_host and preferred_host not in {a["address"] for a in lan_addresses()}:
                raise ValueError("所选地址已不在本机网卡上，请刷新地址列表后重试")
            new = {"enabled": enabled, "port": port, "preferred_host": preferred_host}
            current_running = bool(self.task and not self.task.done())
            replacement = None
            if enabled and (not current_running or port != self.config["port"]):
                # Verify the replacement listener before stopping a working one.
                replacement = await self._start(port)
            try:
                self.persist(new)
            except OSError:
                if replacement:
                    await self._stop(*replacement)
                raise ValueError("局域网设置无法保存，请检查数据目录权限") from None
            if not enabled or replacement:
                await self._stop(self.server, self.task, self.listener)
                self.server = self.task = self.listener = None
            if replacement:
                self.server, self.task, self.listener = replacement
            self.config, self.error = new, ""
            return self.status()
