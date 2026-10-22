from __future__ import annotations

import atexit
import hashlib
import os
import secrets
from typing import Literal
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from app.main import create_app
from .modules import Strict, Workspace, WorkspaceStore, compose
from .runtime import Runtime
from .network import NetworkMonitor
from .delay import DelayMonitor
from .probe import ProbeManager
from .geo_update import GeoUpdater
from .settings import ClientSettings, lan_addresses


class Apply(Strict):
    profile_id: str
    profile_revision: int
    workspace_revision: int
    mixed_port: int = Field(default=17890, ge=1024, le=65535)
    tun: bool = False
    tun_stack: Literal["mixed", "system", "gvisor"] = "mixed"
    proxy_mode: Literal["system", "tun", "manual"] | None = None


class Select(Strict):
    name: str = Field(min_length=1, max_length=200)


class ProxyChange(Strict):
    enabled: bool


class TunChange(ProxyChange):
    stack: Literal["mixed", "system", "gvisor"] = "mixed"


class ModeChange(Strict):
    mode: Literal["system", "tun", "manual"]
    stack: Literal["mixed", "system", "gvisor"] = "mixed"


class DelayRequest(Strict):
    name: str = Field(min_length=1, max_length=200)
    endpoint: Literal["cloudflare", "gstatic"] = "cloudflare"
    timeout_ms: int = Field(default=5000, ge=1000, le=10000)
    profile_id: str | None = None
    profile_revision: int | None = None
    workspace_revision: int | None = None


class ProbeRequest(Strict):
    profile_id: str


def build_app(home: Path):
    app = create_app(home / "data")
    workspace = WorkspaceStore(home / "data" / "workspace.json")
    runtime = Runtime(home)
    network = NetworkMonitor(runtime)
    delay = DelayMonitor(runtime)
    probe, geodata = ProbeManager(runtime), GeoUpdater(runtime)
    app.state.runtime = runtime
    app.state.workspace = workspace
    def cleanup():
        geodata.close()
        runtime.stop()
        runtime.elevation.close()
        probe.stop()
    atexit.register(cleanup)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            try:
                yield
            finally:
                cleanup()

    app.router.lifespan_context = lifespan

    desktop_token = os.environ.get("CLASH_STUDIO_DESKTOP_TOKEN", "")

    @app.middleware("http")
    async def desktop_guard(request, call_next):
        if desktop_token and request.url.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("X-Clash-Desktop-Token", ""), desktop_token):
                return JSONResponse({"detail": "此配置服务由 Tauri 桌面程序独占管理"}, status_code=403)
        return await call_next(request)

    def row(profile_id):
        value = app.state.store.get(profile_id)
        if value is None:
            raise HTTPException(404, "订阅不存在")
        return value

    def profile_config(profile_id):
        profile = row(profile_id)
        state = workspace.load()
        result = compose(profile["published"], profile_id, state)
        return profile, result

    def settings_payload():
        return {"settings": runtime.settings.load().model_dump(), "lan_addresses": lan_addresses(),
                "core_version": runtime.core_version(), "geodata": geodata.status()}

    @app.get("/api/client/settings")
    def get_settings():
        return settings_payload()

    @app.put("/api/client/settings")
    def save_settings(body: ClientSettings):
        probe.stop()
        with runtime.lock:
            previous = runtime.settings.load()
            runtime.settings.save(body)
            try:
                if runtime.alive() and runtime.active:
                    runtime.apply(runtime.last_composed, runtime.active_row, body.mixed_port or runtime.active["mixed_port"],
                                  runtime.active.get("tun", False), runtime.active.get("tun_stack", "mixed"))
            except BaseException:
                runtime.settings.save(previous)
                raise
        return settings_payload()

    @app.get("/api/client/geodata")
    def get_geodata():
        return geodata.status()

    @app.post("/api/client/geodata/update")
    def update_geodata():
        probe.stop()
        return geodata.start()

    @app.post("/api/client/geodata/cancel")
    def cancel_geodata():
        return geodata.cancel()

    @app.get("/api/client/proxy-catalog")
    def proxy_catalog(profile_id: str):
        profile, composed = profile_config(profile_id)
        active = runtime.active if runtime.alive() else None
        live = bool(active and active["profile_id"] == profile_id and active["revision"] == profile["revision"] and active["workspace_revision"] == composed["workspace_revision"])
        value = {"proxies": runtime.request("GET", "/proxies").get("proxies", {}), "has_providers": False} if live else probe.read_catalog(composed["config"])
        return {**value, "live": live, "profile_revision": profile["revision"], "workspace_revision": composed["workspace_revision"],
                "key": f"{profile_id}:{profile['revision']}:{composed['workspace_revision']}:{runtime.settings.load().ipv6}:{live}"}

    @app.post("/api/client/probe/prepare")
    def prepare_probe(body: ProbeRequest):
        _, composed = profile_config(body.profile_id)
        probe.ensure(composed["config"])
        return {"ready": True}

    @app.post("/api/client/probe/stop")
    def stop_probe():
        probe.stop()
        return {"stopped": True}

    @app.get("/api/client/info")
    def info():
        return {"app": "clash-studio-alpha", "version": "0.5.1", "platform": "windows-x64", "desktop": bool(desktop_token),
                "instance": hashlib.sha256(str(home.resolve()).casefold().encode()).hexdigest()[:16]}

    @app.get("/api/client/workspace")
    def get_workspace():
        return workspace.load()

    @app.put("/api/client/workspace")
    def save_workspace(body: Workspace):
        return workspace.save(body)

    @app.get("/api/client/preview/{profile_id}")
    def preview(profile_id: str):
        profile = row(profile_id)
        result = compose(profile["published"], profile_id, workspace.load())
        result.update(profile_revision=profile["revision"], published_conflict=bool(profile["last_error"]))
        return result

    @app.get("/api/client/runtime")
    def get_runtime():
        return runtime.status()

    @app.get("/api/client/network/ip")
    def public_ip(route: Literal["system", "proxy"] = "system", refresh: bool = False):
        return network.lookup(route, refresh)

    @app.get("/api/client/network/traffic")
    def traffic():
        return network.counters()

    @app.post("/api/client/runtime/elevate")
    def elevate_runtime():
        runtime.elevation.ensure()
        runtime.event("管理员助手已连接，主窗口无需重启")
        return runtime.status()

    @app.post("/api/client/runtime/apply")
    def apply(body: Apply):
        probe.stop()
        if geodata.busy():
            raise HTTPException(409, "GeoData 更新中，请等待完成或取消后再启动内核")
        profile, state = row(body.profile_id), workspace.load()
        if profile["revision"] != body.profile_revision or state.revision != body.workspace_revision:
            raise HTTPException(409, "预览后配置发生变化，请重新预览后再应用")
        if profile["last_error"]:
            raise HTTPException(422, "订阅存在未处理的更新冲突，请在配置编辑器中处理后再应用")
        with runtime.lock:
            if geodata.busy():
                raise HTTPException(409, "GeoData 更新中，请等待完成或取消后再启动内核")
            tun = body.proxy_mode == "tun" if body.proxy_mode is not None else body.tun
            result = runtime.apply(compose(profile["published"], body.profile_id, state), profile, body.mixed_port, tun, body.tun_stack)
            if body.proxy_mode is not None:
                return runtime.change_mode(body.proxy_mode, body.tun_stack)
            return result

    @app.put("/api/client/runtime/mode")
    def change_mode(body: ModeChange):
        probe.stop()
        return runtime.change_mode(body.mode, body.stack)

    @app.post("/api/client/runtime/delay")
    def probe_delay(body: DelayRequest):
        if body.profile_id:
            profile, composed = profile_config(body.profile_id)
            if body.profile_revision != profile["revision"] or body.workspace_revision != composed["workspace_revision"]:
                raise HTTPException(409, "节点配置已变化，请刷新节点列表后重新测速")
            active = runtime.active if runtime.alive() else None
            if not (active and active["profile_id"] == body.profile_id and active["revision"] == profile["revision"] and active["workspace_revision"] == composed["workspace_revision"]):
                return probe.measure(composed["config"], body.name, body.endpoint, body.timeout_ms)
        return delay.probe(body.name, body.endpoint, body.timeout_ms)

    @app.put("/api/client/runtime/tun")
    def change_tun(body: TunChange):
        probe.stop()
        return runtime.change_tun(body.enabled, body.stack)

    @app.post("/api/client/runtime/stop")
    def stop():
        probe.stop()
        return runtime.stop()

    @app.put("/api/client/runtime/system-proxy")
    def system_proxy(body: ProxyChange):
        with runtime.lock:
            if body.enabled:
                if not runtime.alive() or runtime.active is None:
                    raise HTTPException(409, "请先启动内核")
                runtime.proxy.enable(runtime.active["mixed_port"])
                runtime.event("已按用户操作开启 Windows 系统代理")
            else:
                result = runtime.proxy.restore()
                if not result["restored"] and runtime.proxy.path.exists():
                    raise HTTPException(409, result["reason"])
                runtime.event("已恢复系统代理")
        return runtime.status()

    @app.get("/api/client/runtime/proxies")
    def proxies():
        return runtime.request("GET", "/proxies")

    @app.put("/api/client/runtime/proxies/{group:path}")
    def select_proxy(group: str, body: Select):
        runtime.request("PUT", "/proxies/" + quote(group, safe=""), json={"name": body.name})
        runtime.event(f"已切换策略组「{group}」")
        return {"selected": True}

    @app.get("/api/client/runtime/connections")
    def connections():
        return runtime.request("GET", "/connections")

    @app.delete("/api/client/runtime/connections/{connection_id}")
    def close_connection(connection_id: str):
        runtime.request("DELETE", "/connections/" + quote(connection_id, safe=""))
        return {"closed": True}

    # Replace only the original static frontend with the alpha build.
    app.router.routes = [route for route in app.router.routes if getattr(route, "name", "") not in ("index", "assets")]
    dist = home / "frontend" / "dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (dist / "index.html").exists():
            raise HTTPException(503, "请先构建 clashstudio/frontend")
        return FileResponse(dist / "index.html")

    return app
