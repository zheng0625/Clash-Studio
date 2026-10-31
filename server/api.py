from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
import secrets
import threading
import time
from collections import deque
from typing import Literal
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from app.main import create_app
from .modules import Strict, Workspace, WorkspaceStore, compose
from .runtime import Runtime
from .network import NetworkMonitor
from .resources import ResourceMonitor
from .dns_summary import summarize_dns
from app.engine import parse_config
from .delay import DelayMonitor
from .probe import ProbeManager
from .geo_update import GeoUpdater
from .settings import ClientSettings, lan_addresses
from .paths import AppPaths
from .cache import CacheBusy, RevisionCache
from .operations import Operations, operation_id
from .logs import FailureLog
from .contracts import envelope
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from app.store import StaleRevision


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


class Selection(Select):
    profile_id: str
    profile_revision: int
    workspace_revision: int
    group: str = Field(min_length=1, max_length=200)


class ProxyChange(Strict):
    enabled: bool


class TunChange(ProxyChange):
    stack: Literal["mixed", "system", "gvisor"] = "mixed"


class ModeChange(Strict):
    mode: Literal["system", "tun", "manual"]
    stack: Literal["mixed", "system", "gvisor"] = "mixed"


class RoutingModeChange(Strict):
    mode: Literal['rule', 'global', 'direct']


class TrayContext(Strict):
    profile_id: str = ''
    proxy_mode: Literal['system', 'tun'] = 'system'
    tun_stack: Literal['mixed', 'system', 'gvisor'] = 'mixed'
    mixed_port: int = Field(default=17890, ge=1024, le=65535)


class TrayAction(Strict):
    action: Literal['toggle', 'rule', 'global', 'direct', 'system', 'tun']


class DelayRequest(Strict):
    name: str = Field(min_length=1, max_length=200)
    endpoint: Literal["cloudflare", "gstatic"] = "cloudflare"
    timeout_ms: int = Field(default=5000, ge=1000, le=10000)
    profile_id: str | None = None
    profile_revision: int | None = None
    workspace_revision: int | None = None


class ProbeRequest(Strict):
    profile_id: str


def build_app(home: Path, data_dir: Path | None = None):
    paths = AppPaths.for_app(home, data_dir)
    paths.data.mkdir(parents=True, exist_ok=True)
    app = create_app(paths.data)
    workspace = WorkspaceStore(paths.data / "workspace.json")
    runtime = Runtime(home, data_dir=paths.data)
    network = NetworkMonitor(runtime)
    resources = ResourceMonitor(runtime)
    delay = DelayMonitor(runtime)
    probe, geodata = ProbeManager(runtime), GeoUpdater(runtime)
    app.state.runtime = runtime
    app.state.workspace = workspace
    compositions = RevisionCache()
    failures = FailureLog(paths.data / 'backend-errors.log')
    operations = Operations(failures=failures)
    app.state.compositions = compositions
    app.state.operations = operations
    closing = threading.Event()
    cleaned = threading.Event()
    def cleanup():
        if cleaned.is_set():
            return
        cleaned.set()
        closing.set()
        operations.close()
        # Restore owned WinINET settings before downloads or core cleanup can wait.
        try:
            runtime.proxy.restore()
        finally:
            workers = [threading.Thread(target=fn, daemon=True) for fn in (geodata.close, probe.stop)]
            for worker in workers:
                worker.start()
            try:
                runtime.stop(final_sample=False, report=False)
            finally:
                runtime.elevation.close()
                for worker in workers:
                    worker.join(timeout=2)
                failures.close()
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

    @app.exception_handler(StarletteHTTPException)
    async def http_failure(request, error):
        return JSONResponse(envelope(error.status_code, error.detail, operation_id.get()), status_code=error.status_code, headers=error.headers)

    @app.exception_handler(StaleRevision)
    async def stale_failure(request, error):
        return JSONResponse(envelope(409, '配置版本已改变，请刷新后重试', operation_id.get()), status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        detail = [{key: item[key] for key in ('loc', 'msg', 'type')} for item in error.errors()]
        return JSONResponse(envelope(422, detail, operation_id.get()), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_failure(request, error):
        failures.record(error, operation_id.get() or getattr(request.state, 'operation_id', None), 'request')
        return JSONResponse(envelope(500, '操作未完成，请查看运行诊断后重试', operation_id.get() or getattr(request.state, 'operation_id', None)), status_code=500)

    desktop_token = os.environ.get("CLASH_STUDIO_DESKTOP_TOKEN", "")

    request_metrics = {name: deque(maxlen=256) for name in ("status", "control", "other")}

    @app.middleware("http")
    async def desktop_guard(request, call_next):
        if desktop_token and request.url.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("X-Clash-Desktop-Token", ""), desktop_token):
                return JSONResponse(envelope(403, "此配置服务由 Tauri 桌面程序独占管理", secrets.token_hex(12)), status_code=403)
        if closing.is_set() and request.method not in ('GET', 'HEAD') and request.url.path not in ('/api/shutdown', '/api/client/prepare-exit'):
            return JSONResponse(envelope(503, '软件正在退出', secrets.token_hex(12)), status_code=503)
        if request.method == 'POST' and request.url.path in ('/api/client/runtime/stop', '/api/client/probe/stop', '/api/client/prepare-exit', '/api/shutdown'):
            probe.cancel_pending()
        request.state.probe_ticket = probe.ticket()
        started = time.perf_counter()
        request.state.operation_id = secrets.token_hex(12)
        token = operation_id.set(request.state.operation_id)
        try:
            response = await call_next(request)
            response.headers['X-Operation-Id'] = operation_id.get()
            category = 'status' if request.url.path == '/api/client/runtime' else 'control' if request.url.path.startswith('/api/client/runtime/') and request.method != 'GET' else 'other'
            request_metrics[category].append((time.perf_counter() - started) * 1000)
            return response
        finally:
            operation_id.reset(token)

    @app.post('/api/client/prepare-exit')
    def prepare_exit():
        closing.set()
        return runtime.proxy.restore()

    def row(profile_id):
        value = app.state.store.get(profile_id)
        if value is None:
            raise HTTPException(404, "订阅不存在")
        return value

    def cached_composition(key, build):
        try:
            return compositions.get(key, build)
        except CacheBusy as error:
            raise HTTPException(503, '配置合成繁忙，请稍后重试') from error

    def profile_config(profile_id):
        profile = row(profile_id)
        state = workspace.load()
        result = cached_composition((profile_id, profile["revision"], state.revision),
                                    lambda: compose(profile["published"], profile_id, state))
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
        with runtime.lifecycle_lock:
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
        if not live:
            runtime.selections.overlay(profile_id, value['proxies'])
        return {**value, "live": live, "profile_revision": profile["revision"], "workspace_revision": composed["workspace_revision"],
                "key": f"{profile_id}:{profile['revision']}:{composed['workspace_revision']}:{runtime.settings.load().ipv6}:{live}"}

    @app.put('/api/client/proxy-selection')
    def save_selection(body: Selection):
        with runtime.lifecycle_lock:
            profile, composed = profile_config(body.profile_id)
            if profile['revision'] != body.profile_revision or composed['workspace_revision'] != body.workspace_revision:
                raise HTTPException(409, '配置已变更，请刷新节点列表后重试')
            active = runtime.active if runtime.alive() else None
            live = bool(active and active['profile_id'] == body.profile_id and active['revision'] == body.profile_revision
                        and active['workspace_revision'] == body.workspace_revision)
            proxies = runtime.request('GET', '/proxies').get('proxies', {}) if live else probe.read_catalog(composed['config'])['proxies']
            group = proxies.get(body.group, {})
            if group.get('type') != 'Selector' or body.name not in group.get('all', []):
                raise HTTPException(422, '只能选择手动策略组中的有效节点，请刷新节点列表')
            if live:
                runtime.request('PUT', '/proxies/' + quote(body.group, safe=''), json={'name': body.name})
            try:
                runtime.selections.set(body.profile_id, body.group, body.name)
            except OSError:
                if live and group.get('now'):
                    runtime.request('PUT', '/proxies/' + quote(body.group, safe=''), json={'name': group['now']})
                raise HTTPException(503, '节点选择保存失败，请检查数据目录权限') from None
            if live:
                runtime.invalidate_egress()
            return {'selected': True, 'live': live, 'group': body.group, 'name': body.name}

    @app.post("/api/client/probe/prepare")
    def prepare_probe(body: ProbeRequest, request: Request):
        _, composed = profile_config(body.profile_id)
        probe.ensure(composed["config"], request.state.probe_ticket)
        return {"ready": True}

    @app.post("/api/client/probe/stop")
    def stop_probe():
        probe.stop()
        return {"stopped": True}

    @app.get("/api/client/info")
    def info():
        identity = str(home.resolve()) if paths.data == home.resolve() / 'data' else str(home.resolve()) + '|' + str(paths.data)
        return {"app": "clash-studio", "version": "1.3.0", "platform": runtime.platform.info['id'], "desktop": bool(desktop_token),
                "platform_info": runtime.platform.info, "paths": paths.describe(),
                "instance": hashlib.sha256((identity.casefold() if os.name == 'nt' else identity).encode()).hexdigest()[:16]}

    @app.get('/api/client/platform')
    def platform_contract():
        return {'schema_version': 1, **runtime.platform.info, 'paths': paths.describe()}

    @app.get("/api/client/workspace")
    def get_workspace():
        return workspace.load()

    @app.put("/api/client/workspace")
    def save_workspace(body: Workspace):
        return workspace.save(body)

    @app.get("/api/client/preview/{profile_id}")
    def preview(profile_id: str):
        profile, result = profile_config(profile_id)
        result.update(profile_revision=profile["revision"], published_conflict=bool(profile["last_error"]))
        return result

    @app.get("/api/client/runtime")
    async def get_runtime():
        return runtime.status()

    @app.get("/api/client/network/ip")
    def public_ip(route: Literal["system", "proxy"] = "system", refresh: bool = False):
        return network.lookup(route, refresh)

    @app.get("/api/client/network/traffic")
    def traffic():
        return network.counters()

    @app.get('/api/client/resources/memory')
    def resource_memory():
        return resources.memory()

    @app.get('/api/client/network/dns-summary')
    def dns_summary(profile_id: str = '', tun: bool = False):
        # Read the applied snapshot while running; never relabel a selected draft
        # as active. The lifecycle lock keeps snapshot identity and YAML atomic.
        with runtime.lifecycle_lock:
            if runtime.alive() and runtime.active:
                config = parse_config((runtime.directory / 'active.yaml').read_text(encoding='utf-8'))
                identity = runtime.active
                return {**summarize_dns(config), 'source': 'runtime',
                        'profile_id': identity['profile_id'], 'config_hash': identity['hash']}
            if not profile_id:
                return {'status': 'unavailable', 'nameservers': [], 'source': 'selected', 'profile_id': '', 'config_hash': ''}
            profile, composed = profile_config(profile_id)
            payload = runtime.prepare(copy.deepcopy(composed), runtime.settings.load().mixed_port or 17890, tun=tun)
            return {**summarize_dns(parse_config(payload)), 'source': 'selected',
                    'profile_id': profile['id'], 'config_hash': hashlib.sha256(payload.encode()).hexdigest()[:12]}

    @app.post("/api/client/runtime/elevate")
    def elevate_runtime():
        runtime.elevation.ensure()
        runtime.event("Linux 内核网络权限已就绪，主窗口无需重启" if runtime.platform.info['os'] == 'linux' else "管理员助手已连接，主窗口无需重启")
        return runtime.status()

    @app.post("/api/client/runtime/apply")
    async def request_apply(body: Apply, background: bool = False):
        if background:
            return JSONResponse(operations.submit('apply', lambda: apply(body, False), runtime.request_cancel), status_code=202)
        return await run_in_threadpool(apply, body, False)

    def apply(body: Apply, background: bool = False):
        if background:
            return JSONResponse(operations.submit('apply', lambda: apply(body, False), runtime.request_cancel), status_code=202)
        with runtime.lock:
            epoch = runtime._cancel_epoch
        probe.stop()
        if geodata.busy():
            raise HTTPException(409, "GeoData 更新中，请等待完成或取消后再启动内核")
        profile, state = row(body.profile_id), workspace.load()
        if profile["revision"] != body.profile_revision or state.revision != body.workspace_revision:
            raise HTTPException(409, "预览后配置发生变化，请重新预览后再应用")
        if profile["last_error"]:
            raise HTTPException(422, "订阅存在未处理的更新冲突，请在配置编辑器中处理后再应用")
        tun = body.proxy_mode == "tun" if body.proxy_mode is not None else body.tun
        def revalidate():
            if geodata.busy():
                raise HTTPException(409, 'GeoData 更新中，请等待完成或取消后再启动内核')
            if row(body.profile_id)['revision'] != body.profile_revision or workspace.load().revision != body.workspace_revision:
                raise HTTPException(409, '应用准备期间配置发生变化，请重新预览')
        composed = cached_composition((body.profile_id, profile['revision'], state.revision), lambda: compose(profile['published'], body.profile_id, state))
        mode = body.proxy_mode
        if mode is None and not tun and runtime.platform.info['os'] == 'linux' and runtime.platform.info['capabilities']['system_proxy']:
            mode = 'system'
        return runtime.apply(composed, profile, body.mixed_port, tun, body.tun_stack, validator=revalidate, capture_mode=mode, expected_epoch=epoch)

    @app.put("/api/client/runtime/mode")
    def change_mode(body: ModeChange):
        probe.stop()
        return runtime.change_mode(body.mode, body.stack)

    @app.put('/api/client/runtime/routing-mode')
    def change_routing_mode(body: RoutingModeChange):
        return runtime.change_routing_mode(body.mode)

    tray_path = paths.data / 'tray-context.json'
    tray_lock = threading.RLock()

    def read_tray_context():
        try:
            return TrayContext.model_validate_json(tray_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return TrayContext()

    def write_tray_context(context):
        temporary = tray_path.with_suffix('.tmp')
        temporary.write_text(context.model_dump_json(), encoding='utf-8')
        temporary.replace(tray_path)

    @app.put('/api/client/tray/context')
    def tray_context(body: TrayContext):
        with tray_lock:
            if body.profile_id:
                row(body.profile_id)
            write_tray_context(body)
            return {'saved': True}

    @app.get('/api/client/tray')
    def tray_state():
        state = runtime.status()
        context = read_tray_context()
        enabled = bool(state['running'] and (state['proxy'].get('owned') or state['tun']['enabled'] or not runtime.platform.info['capabilities']['system_proxy']))
        mode = 'tun' if state['tun']['enabled'] else 'system' if state['proxy'].get('owned') else context.proxy_mode
        return {'enabled': enabled, 'running': state['running'], 'proxy_mode': mode, 'capabilities': runtime.platform.info['capabilities'],
                'context_configured': tray_path.exists(), 'profile_id': context.profile_id, 'tun_stack': context.tun_stack,
                'routing_mode': state['routing_mode'],
                'can_start': bool(state['running'] or (context.profile_id and app.state.store.get(context.profile_id)))}

    @app.post('/api/client/tray/action')
    def tray_action(body: TrayAction):
        with tray_lock:
            context = read_tray_context()
            if body.action in ('rule', 'global', 'direct'):
                runtime.change_routing_mode(body.action)
            elif body.action in ('system', 'tun'):
                if runtime.alive():
                    change_mode(ModeChange(mode=body.action, stack=context.tun_stack))
                write_tray_context(context.model_copy(update={'proxy_mode': body.action}))
            elif tray_state()['enabled']:
                stop()
            elif runtime.alive():
                change_mode(ModeChange(mode=context.proxy_mode, stack=context.tun_stack))
            else:
                if not context.profile_id:
                    raise HTTPException(409, '请先在主窗口选择订阅配置')
                profile = row(context.profile_id)
                apply(Apply(profile_id=profile['id'], profile_revision=profile['revision'],
                            workspace_revision=workspace.load().revision,
                            mixed_port=runtime.settings.load().mixed_port or context.mixed_port,
                            proxy_mode=context.proxy_mode if context.proxy_mode == 'tun' or runtime.platform.info['capabilities']['system_proxy'] else 'manual', tun_stack=context.tun_stack))
            return tray_state()

    @app.post("/api/client/runtime/delay")
    def probe_delay(body: DelayRequest, request: Request):
        probe.check_ticket(request.state.probe_ticket)
        if body.profile_id:
            profile, composed = profile_config(body.profile_id)
            if body.profile_revision != profile["revision"] or body.workspace_revision != composed["workspace_revision"]:
                raise HTTPException(409, "节点配置已变化，请刷新节点列表后重新测速")
            active = runtime.active if runtime.alive() else None
            if not (active and active["profile_id"] == body.profile_id and active["revision"] == profile["revision"] and active["workspace_revision"] == composed["workspace_revision"]):
                return probe.measure(composed["config"], body.name, body.endpoint, body.timeout_ms, request.state.probe_ticket)
        return delay.probe(body.name, body.endpoint, body.timeout_ms)

    @app.put("/api/client/runtime/tun")
    def change_tun(body: TunChange):
        probe.stop()
        return runtime.change_tun(body.enabled, body.stack)

    @app.post("/api/client/runtime/stop")
    async def request_stop(background: bool = False):
        runtime.request_cancel()
        operations.cancel_applies()
        if background:
            return JSONResponse(operations.submit('stop', lambda: stop(False)), status_code=202)
        return await run_in_threadpool(stop, False)

    def stop(background: bool = False):
        runtime.request_cancel()
        operations.cancel_applies()
        if background:
            return JSONResponse(operations.submit('stop', lambda: stop(False)), status_code=202)
        probe.stop()
        return runtime.stop()

    @app.put("/api/client/runtime/system-proxy")
    def system_proxy(body: ProxyChange):
        with runtime.lifecycle_lock:
            if body.enabled:
                if not runtime.alive() or runtime.active is None:
                    raise HTTPException(409, "请先启动内核")
                runtime.proxy.enable(runtime.active["mixed_port"])
                runtime.event("已按用户操作开启 系统代理")
            else:
                result = runtime.proxy.restore()
                if not result["restored"] and runtime.proxy.path.exists():
                    raise HTTPException(409, result["reason"])
                runtime.event("已恢复系统代理")
        runtime.refresh_proxy_status()
        return runtime.status()

    @app.get("/api/client/runtime/proxies")
    def proxies():
        return runtime.proxies()

    @app.put("/api/client/runtime/proxies/{group:path}")
    def select_proxy(group: str, body: Select):
        with runtime.lifecycle_lock:
            if not runtime.alive() or not runtime.active:
                raise HTTPException(409, '内核未启动')
            return save_selection(Selection(**body.model_dump(), group=group, profile_id=runtime.active['profile_id'],
                                           profile_revision=runtime.active['revision'], workspace_revision=runtime.active['workspace_revision']))

    @app.get("/api/client/runtime/connections")
    def connections():
        return Response(runtime.connection_json(), media_type="application/json")

    @app.delete("/api/client/runtime/connections/{connection_id}")
    def close_connection(connection_id: str):
        runtime.request("DELETE", "/connections/" + quote(connection_id, safe=""))
        runtime.invalidate_connections()
        return {"closed": True}

    @app.get('/api/client/operations/{key}')
    async def operation_status(key: str):
        return operations.get(key)

    @app.delete('/api/client/operations/{key}')
    async def cancel_operation(key: str):
        return operations.cancel(key)

    @app.get('/api/client/diagnostics')
    async def diagnostics():
        samples = {name: sorted(list(values)) for name, values in request_metrics.items()}
        samples['state_lock_wait'] = sorted(list(runtime._status_lock_wait))
        latency = {name: {'count': len(values), 'p50': round(values[int((len(values)-1)*.5)], 2) if values else None, 'p95': round(values[int((len(values)-1)*.95)], 2) if values else None} for name, values in samples.items()}
        return {'schema_version': 1, 'sampled_at': __import__('time').time(),
                'operation': runtime.status()['operation'], 'composition_cache': compositions.stats(), 'operations': operations.stats(), 'request_ms': latency}

    # Replace only the original static frontend with the production build.
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
