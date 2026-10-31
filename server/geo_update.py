"""Explicit GeoData updates from the upstream project's documented CDN."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time

import httpx
from fastapi import HTTPException

FILES = {"Country.mmdb": "country.mmdb", "geoip.dat": "geoip.dat", "geosite.dat": "geosite.dat", "ASN.mmdb": "GeoLite2-ASN.mmdb"}
SOURCES = ["https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/",
           "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/"]


class GeoUpdater:
    def __init__(self, runtime):
        self.runtime, self.lock = runtime, threading.RLock()
        self.cancelled = threading.Event()
        self.thread = None
        self.state = {"busy": False, "phase": "idle", "completed": 0, "total": 4, "file": "", "message": ""}

    def status(self):
        with self.lock:
            files = []
            for name in FILES:
                path = self.runtime.directory / name
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    stat = None
                files.append({"name": name, "installed": stat is not None, "bytes": stat.st_size if stat else 0,
                              "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else ""})
            return {**self.state, "files": files}

    def busy(self):
        with self.lock:
            return self.state["busy"]

    def update_state(self, **values):
        with self.lock:
            self.state.update(values)

    def start(self):
        with self.runtime.lock, self.lock:
            if self.state["busy"]:
                raise HTTPException(409, "GeoData 更新已在进行")
            if self.runtime.alive():
                raise HTTPException(409, "请先停止主内核，再更新 GeoData")
            self.cancelled.clear()
            self.state.update(busy=True, phase="downloading", completed=0, file="", message="正在从上游 CDN 下载并校验")
            try:
                self.thread = threading.Thread(target=self.run, daemon=True)
                self.thread.start()
            except Exception:
                self.thread = None
                self.state.update(busy=False, phase="error", message="更新任务未能启动，请稍后重试")
                raise HTTPException(503, "更新任务未能启动，请稍后重试") from None
        return self.status()

    def cancel(self):
        self.cancelled.set()
        return self.status()

    def close(self):
        self.cancelled.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def download(self, client, url, path, limit):
        start = time.monotonic()
        digest, size = hashlib.sha256(), 0
        with client.stream("GET", url) as response, path.open("wb") as output:
            response.raise_for_status()
            for chunk in response.iter_bytes(65536):
                if self.cancelled.is_set():
                    raise InterruptedError()
                size += len(chunk)
                if size > limit or time.monotonic() - start > 90:
                    raise ValueError("Download limit")
                output.write(chunk)
                digest.update(chunk)
        return digest.hexdigest(), size

    def run(self):
        staging_root = stage = None
        installed = []
        temporary_files = []
        rollback_ok = True
        try:
            staging_root = (self.runtime.paths.data / "geodata-updates").resolve()
            stage = staging_root / secrets.token_hex(8)
            stage.mkdir(parents=True)
            metadata = []
            with httpx.Client(trust_env=False, follow_redirects=True, timeout=httpx.Timeout(15, connect=8)) as client:
                for index, (name, remote) in enumerate(FILES.items()):
                    self.update_state(file=name)
                    if self.cancelled.is_set():
                        raise InterruptedError()
                    for base in SOURCES:
                        try:
                            checksum = stage / (name + ".sha256sum")
                            self.download(client, base + remote + ".sha256sum", checksum, 16384)
                            match = re.search(r"\b[0-9a-fA-F]{64}\b", checksum.read_text(encoding="utf-8"))
                            if not match:
                                raise ValueError("Invalid checksum")
                            digest, size = self.download(client, base + remote, stage / name, 64 * 1024 * 1024)
                            if digest != match.group(0).lower() or size < 1024:
                                raise ValueError("Checksum mismatch")
                            if name.endswith(".mmdb") and b"\xab\xcd\xefMaxMind.com" not in (stage / name).read_bytes()[-131072:]:
                                raise ValueError("Invalid MMDB")
                            metadata.append({"name": name, "sha256": digest, "bytes": size, "url": base + remote})
                            break
                        except (httpx.HTTPError, ValueError, OSError):
                            if self.cancelled.is_set():
                                raise InterruptedError()
                    else:
                        raise ValueError("数据库下载或摘要校验失败，原数据已保留")
                    self.update_state(completed=index + 1)
            if self.cancelled.is_set():
                raise InterruptedError()
            manifest = {"origin": "MetaCubeX/meta-rules-dat documented CDN; SHA-256 sidecars verified", "updated_at": datetime.now(timezone.utc).isoformat(), "files": metadata}
            (stage / "source.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            with self.runtime.lock:
                if self.runtime.alive():
                    raise ValueError("主内核运行中，未替换数据库，请停止后重试")
                self.update_state(phase="installing", message="正在替换已校验数据库")
                targets = [(stage / name, directory / name) for directory in (self.runtime.home / "bin" / "geodata", self.runtime.directory) for name in FILES]
                targets.append((stage / "source.json", self.runtime.home / "bin" / "geodata" / "source.json"))
                for index, (source, destination) in enumerate(targets):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    backup = stage / f"backup-{index}"
                    existed = destination.exists()
                    if existed:
                        shutil.copy2(destination, backup)
                    temporary = destination.with_name(destination.name + ".update")
                    temporary_files.append(temporary)
                    shutil.copyfile(source, temporary)
                    installed.append((destination, backup, existed))
                    os.replace(temporary, destination)
            self.update_state(phase="done", message="四项数据库已更新，下次启动内核使用新数据")
        except InterruptedError:
            self.update_state(phase="cancelled", message="更新已取消，原数据保留")
        except Exception:
            for destination, backup, existed in reversed(installed):
                try:
                    if existed:
                        shutil.copy2(backup, destination)
                    else:
                        destination.unlink(missing_ok=True)
                except OSError:
                    rollback_ok = False
            self.update_state(phase="error", message="更新失败（" + self.state.get("file", "数据库") + "），已尝试回退原文件；请检查 CDN 联网和目录权限")
        finally:
            try:
                for temporary in temporary_files:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
                # Failed rollback backups are recovery material, not disposable cache.
                if rollback_ok and stage is not None and stage.resolve().parent == staging_root and not stage.is_symlink():
                    shutil.rmtree(stage, ignore_errors=True)
            finally:
                self.update_state(busy=False, file="")
