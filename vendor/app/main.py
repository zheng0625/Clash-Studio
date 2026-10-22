from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import MAX_BYTES, compile_config, empty_edits, parse_config, plain
from .ai_rules import catalogue
from .ai_preset import create_ai_draft
from .lan import LanController, build_lan_app, is_lan_ipv4
from .store import StaleRevision, Store, now
from .paths import RESOURCE_ROOT, default_data_dir, instance_id
from .version import VERSION

ROOT = RESOURCE_ROOT
# Subscription panels commonly select their output from the client User-Agent.
# Match the official Clash Verge Rev subscription request format, rather than
# the previous unrecognised "ClashStudio/0.1 mihomo" identifier.
SUBSCRIPTION_USER_AGENT = "clash-verge/v2.5.8"


def reject_client_notice(source: str):
    try:
        config = parse_config(source)
    except ValueError:
        # Let the normal parser report malformed YAML at the import/refresh step.
        return
    if config.get("proxies") or config.get("proxy-providers"):
        return
    messages = [group["name"] for group in config.get("proxy-groups", [])]
    messages.extend(member for group in config.get("proxy-groups", []) for member in group.get("proxies", []))
    if any("下载" in message and any(client in message.lower() for client in ("clash", "mihomo", "客户端")) for message in messages):
        raise HTTPException(502, "上游返回了下载客户端的提示配置，没有提供实际节点。请检查订阅状态，或从服务商获取 Clash/Mihomo 专用订阅链接；不会将提示配置发布为有效订阅。")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIRouting(StrictModel):
    group: str = Field(min_length=1, max_length=200)
    enabled: bool = True


class Edits(StrictModel):
    proxy_renames: dict[str, str] = Field(default_factory=dict)
    excluded_proxies: list[str] = Field(default_factory=list)
    group_overrides: dict[str, dict] = Field(default_factory=dict)
    deleted_groups: list[str] = Field(default_factory=list)
    new_groups: list[dict] = Field(default_factory=list)
    removed_rules: list[str] = Field(default_factory=list)
    added_rules: list[str] = Field(default_factory=list)
    rule_order: list[str] = Field(default_factory=list)
    ai_routing: AIRouting | None = None

    @field_validator("group_overrides")
    @classmethod
    def check_patches(cls, value):
        allowed = {"name", "type", "proxies", "use", "url", "interval", "tolerance", "lazy", "strategy", "filter", "exclude-filter", "include-all", "include-all-proxies", "include-all-providers"}
        for patch in value.values():
            if not set(patch) <= allowed:
                raise ValueError("代理组修改包含不支持的字段")
            cls.check_group(patch, False)
        return value

    @staticmethod
    def check_group(group, required):
        for key in ("name", "type", "url", "filter", "exclude-filter", "strategy"):
            if key in group and not isinstance(group[key], str):
                raise ValueError(f"{key} 必须是字符串")
        for key in ("proxies", "use"):
            if key in group and (not isinstance(group[key], list) or any(not isinstance(n, str) for n in group[key])):
                raise ValueError(f"{key} 必须是字符串列表")
        if required and (not group.get("name") or not group.get("type")):
            raise ValueError("新增代理组需要名称和类型")
        plain(group)

    @field_validator("new_groups")
    @classmethod
    def check_new(cls, value):
        for group in value:
            cls.check_group(group, True)
        return value


class ImportBody(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    source_type: Literal["url", "file", "demo"]
    source_url: str = Field(default="", max_length=8192)
    yaml: str = Field(default="", max_length=MAX_BYTES)


class EditBody(StrictModel):
    revision: int
    edits: Edits


class RevisionBody(StrictModel):
    revision: int


class AIPresetBody(EditBody):
    outlet: str = Field(min_length=1, max_length=200)


class RefreshBody(RevisionBody):
    yaml: str | None = Field(default=None, max_length=MAX_BYTES)


class MetaBody(RevisionBody):
    title: str = Field(min_length=1, max_length=100)
    enabled: bool
    interval_minutes: int = Field(ge=0, le=10080)


class NetworkBody(StrictModel):
    enabled: bool
    port: int = Field(ge=1024, le=65535)
    selected_host: str = Field(default="", max_length=50)

    @field_validator("selected_host")
    @classmethod
    def check_host(cls, value):
        if value and not is_lan_ipv4(value):
            raise ValueError("共享地址必须是局域网 IPv4 地址")
        return value


def fetch_source(url: str):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise HTTPException(400, "请输入有效的 HTTP/HTTPS 订阅 URL，不支持 URL 内嵌用户名密码")
        data = bytearray()
        with httpx.Client(timeout=httpx.Timeout(25, connect=12), follow_redirects=True, max_redirects=5,
                          headers={"User-Agent": SUBSCRIPTION_USER_AGENT, "Accept": "text/yaml, text/plain, */*"}) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise HTTPException(502, f"订阅下载失败：上游 HTTP {response.status_code}")
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise HTTPException(413, "订阅内容超过 8 MB")
                headers = {key: response.headers[key] for key in ("subscription-userinfo", "profile-update-interval") if key in response.headers}
        source = bytes(data).decode("utf-8-sig")
        reject_client_notice(source)
        return source, headers
    except HTTPException:
        raise
    except (httpx.HTTPError, UnicodeError, ValueError):
        raise HTTPException(502, "订阅拉取失败：请检查地址、网络、代理环境和 UTF-8 编码；已保留上次可用配置") from None


def create_app(data_dir: Path | None = None):
    store = Store(data_dir or default_data_dir())

    def get_row(sub_id):
        row = store.get(sub_id)
        if not row:
            raise HTTPException(404, "订阅不存在")
        return row

    def summarize(row):
        source = parse_config(row["source"])
        return {key: row[key] for key in ("id", "title", "source_type", "revision", "enabled", "interval_minutes", "created_at", "updated_at", "refreshed_at", "last_error")} | {
            "source_host": urlsplit(row["source_url"]).hostname if row["source_url"] else "本地 YAML",
            "proxy_count": len(source.get("proxies", [])), "group_count": len(source.get("proxy-groups", [])), "rule_count": len(source.get("rules", []))}

    def detail(row):
        edits = json.loads(row["edits"])
        return summarize(row) | {"source_url": row["source_url"], "source": plain(parse_config(row["source"])),
                                 "source_yaml": row["source"], "edits": edits,
                                 "preview": compile_config(row["source"], edits), "subscription_path": f"/sub/{row['token']}"}

    def refresh(sub_id, revision, replacement=None):
        row = get_row(sub_id)
        if row["revision"] != revision:
            raise StaleRevision()
        headers = json.loads(row["source_headers"])
        try:
            if row["source_type"] == "url":
                source, headers = fetch_source(row["source_url"])
            elif replacement is not None:
                source = replacement
            elif row["source_type"] == "demo":
                source = (ROOT / "examples" / "demo.yaml").read_text(encoding="utf-8")
            else:
                raise HTTPException(400, "本地文件订阅需要重新上传 YAML 文件")
            result = compile_config(source, json.loads(row["edits"]))
        except (HTTPException, ValueError) as exc:
            message = exc.detail if isinstance(exc, HTTPException) else str(exc)
            store.update(sub_id, revision, {"last_error": message, "refreshed_at": now()})
            raise HTTPException(400, message) from None
        values = {"source": source, "source_headers": json.dumps(headers), "refreshed_at": now()}
        if result["errors"]:
            values["last_error"] = "更新产生冲突，继续提供上一份可用配置。" + "；".join(result["errors"][:3])
            store.update(sub_id, revision, values)
        else:
            values.update(published=result["yaml"], last_error="")
            store.update(sub_id, revision, values, "刷新源订阅")
        return detail(get_row(sub_id))

    async def schedule():
        while True:
            await asyncio.sleep(30)
            for row in store.list():
                if not row["enabled"] or row["source_type"] != "url" or not row["interval_minutes"]:
                    continue
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(row["refreshed_at"])).total_seconds()
                if age >= row["interval_minutes"] * 60:
                    try:
                        await asyncio.to_thread(refresh, row["id"], row["revision"])
                    except (HTTPException, StaleRevision):
                        pass

    @asynccontextmanager
    async def lifespan(app):
        await network.start()
        task = asyncio.create_task(schedule())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await network.close()

    app = FastAPI(title="Clash Studio", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver", "[::1]"])

    @app.middleware("http")
    async def local_guard(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("x-clash-studio") != "1":
                return JSONResponse({"detail": "缺少本地工作台请求标识"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin not in (str(request.base_url).rstrip("/"), "http://127.0.0.1:5173", "http://localhost:5173"):
                return JSONResponse({"detail": "不允许跨站修改本地配置"}, status_code=403)
        length = request.headers.get("content-length", "0")
        if length.isdigit() and int(length) > MAX_BYTES * 3:
            return JSONResponse({"detail": "请求过大"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(StaleRevision)
    async def stale_handler(request, exc):
        return JSONResponse({"detail": "配置已在其他页面或自动刷新中更新，请重新载入后再保存"}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/api/health")
    def health():
        return {"app": "clash-studio", "status": "ok", "version": VERSION, "mode": "local",
                "pid": os.getpid(), "instance": instance_id(), "data_dir": str(store.path.parent)}

    @app.post("/api/shutdown")
    async def shutdown(request: Request):
        if not request.client or request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(403, "Shutdown requires a loopback connection")
        callback = getattr(app.state, "shutdown_callback", None)
        if callback is None:
            raise HTTPException(503, "Shutdown is available only through the application launcher")
        asyncio.get_running_loop().call_later(0.2, callback)
        return {"status": "stopping"}

    @app.get("/api/network")
    def get_network():
        return network.status()

    @app.put("/api/network")
    async def update_network(body: NetworkBody, request: Request):
        return await network.update(body.enabled, body.port, body.selected_host, request.url.port or 80)

    @app.get("/api/subscriptions")
    def list_subscriptions():
        return [summarize(row) for row in store.list()]

    @app.get("/api/presets/ai")
    def ai_catalogue():
        return catalogue()

    @app.post("/api/subscriptions", status_code=201)
    def import_subscription(body: ImportBody):
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "请输入订阅名称")
        headers = {}
        if body.source_type == "url":
            source, headers = fetch_source(body.source_url.strip())
        elif body.source_type == "demo":
            source = (ROOT / "examples" / "demo.yaml").read_text(encoding="utf-8")
        else:
            source = body.yaml
        edits = empty_edits()
        result = compile_config(source, edits)
        if result["errors"]:
            raise HTTPException(422, {"message": "原配置未通过基础校验", "errors": result["errors"]})
        sub_id = store.create(title, body.source_type, body.source_url.strip() if body.source_type == "url" else "", source, edits, result["yaml"], headers)
        return detail(get_row(sub_id))

    @app.get("/api/subscriptions/{sub_id}")
    def get_subscription(sub_id: str):
        return detail(get_row(sub_id))

    @app.post("/api/subscriptions/{sub_id}/preview")
    def preview(sub_id: str, body: EditBody):
        row = get_row(sub_id)
        if row["revision"] != body.revision:
            raise StaleRevision()
        return compile_config(row["source"], body.edits.model_dump())

    @app.post("/api/subscriptions/{sub_id}/ai-preset")
    def ai_preset(sub_id: str, body: AIPresetBody):
        row = get_row(sub_id)
        if row["revision"] != body.revision:
            raise StaleRevision()
        draft = create_ai_draft(row["source"], body.edits.model_dump(), body.outlet)
        if draft["preview"]["errors"]:
            raise HTTPException(422, {"message": "AI 分流草稿未通过校验", "errors": draft["preview"]["errors"]})
        return draft

    @app.put("/api/subscriptions/{sub_id}/edits")
    def save_edits(sub_id: str, body: EditBody):
        row = get_row(sub_id)
        result = compile_config(row["source"], body.edits.model_dump())
        if result["errors"]:
            raise HTTPException(422, {"message": "请先解决配置错误再保存", "errors": result["errors"]})
        store.update(sub_id, body.revision, {"edits": body.edits.model_dump_json(), "published": result["yaml"], "last_error": ""}, "保存可视化修改")
        return detail(get_row(sub_id))

    @app.post("/api/subscriptions/{sub_id}/refresh")
    def refresh_subscription(sub_id: str, body: RefreshBody):
        return refresh(sub_id, body.revision, body.yaml)

    @app.patch("/api/subscriptions/{sub_id}")
    def update_meta(sub_id: str, body: MetaBody):
        get_row(sub_id)
        if not body.title.strip():
            raise HTTPException(400, "请输入订阅名称")
        store.update(sub_id, body.revision, {"title": body.title.strip(), "enabled": int(body.enabled), "interval_minutes": body.interval_minutes})
        return detail(get_row(sub_id))

    @app.post("/api/subscriptions/{sub_id}/rotate-token")
    def rotate_token(sub_id: str, body: RevisionBody):
        get_row(sub_id)
        store.update(sub_id, body.revision, {"token": secrets.token_urlsafe(24)})
        return detail(get_row(sub_id))

    @app.delete("/api/subscriptions/{sub_id}")
    def delete_subscription(sub_id: str, revision: int):
        get_row(sub_id)
        store.delete(sub_id, revision)
        return {"deleted": True}

    @app.get("/api/subscriptions/{sub_id}/history")
    def history(sub_id: str):
        get_row(sub_id)
        return store.history(sub_id)

    @app.get("/api/subscriptions/{sub_id}/history/{history_id}")
    def history_detail(sub_id: str, history_id: int):
        get_row(sub_id)
        row = store.historical(sub_id, history_id)
        if not row:
            raise HTTPException(404, "历史版本不存在")
        return {"id": row["id"], "label": row["label"], "yaml": row["yaml"], "created_at": row["created_at"]}

    @app.post("/api/subscriptions/{sub_id}/history/{history_id}/restore")
    def restore_history(sub_id: str, history_id: int, body: RevisionBody):
        get_row(sub_id)
        row = store.historical(sub_id, history_id)
        if not row:
            raise HTTPException(404, "历史版本不存在")
        result = compile_config(row["source"], json.loads(row["edits"]))
        if result["errors"]:
            raise HTTPException(422, "历史版本未通过当前校验")
        store.update(sub_id, body.revision, {"source": row["source"], "edits": row["edits"], "published": result["yaml"], "last_error": ""}, f"恢复历史版本 #{history_id}")
        return detail(get_row(sub_id))

    @app.api_route("/sub/{token}", methods=["GET", "HEAD"])
    def serve_subscription(token: str, request: Request):
        row = store.by_token(token)
        if not row:
            raise HTTPException(404, "订阅不存在或已停用")
        headers = {"Content-Disposition": 'inline; filename="clash-studio.yaml"',
                   "Content-Length": str(len(row["published"].encode("utf-8")))}
        for key, value in json.loads(row["source_headers"]).items():
            if key in ("subscription-userinfo", "profile-update-interval") and value.isascii() and "\n" not in value and "\r" not in value:
                headers[key] = value
        return Response(content=row["published"] if request.method == "GET" else b"", media_type="text/yaml; charset=utf-8", headers=headers)

    lan_app = build_lan_app(serve_subscription)
    network = LanController(store.path.parent, lan_app)
    app.state.network = network
    app.state.lan_app = lan_app

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (dist / "index.html").exists():
            return JSONResponse({"detail": "请先构建前端，或运行 start.ps1 完成初始化"}, status_code=503)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
