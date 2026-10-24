from __future__ import annotations

import hashlib
import json
import copy
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.engine import dump_config, parse_config
from .elevation import ElevatedProcess
from .paths import AppPaths
from .platforms import PlatformServices, core_binary, is_admin, other_cores
from .geodata import seed_databases, validation_message
from .settings import SettingsStore, lan_ipv6_networks
from .selections import SelectionStore


class Runtime:
    def __init__(self, home: Path, resource_home: Path | None = None, *, data_dir: Path | None = None):
        self.home = home
        self.resource_home = resource_home or home
        self.paths = AppPaths.for_app(self.resource_home, data_dir if data_dir is not None else home / 'data')
        self.platform = PlatformServices(self.paths)
        self.directory = self.paths.runtime
        self.directory.mkdir(parents=True, exist_ok=True)
        self.binary = core_binary(self.resource_home)
        self.process = None
        self.elevation = self.platform.elevation()
        self.controller_port = 0
        self.secret = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.proxy = self.platform.proxy()
        self.settings = SettingsStore(self.paths.data / "client-settings.json")
        self.selections = SelectionStore(self.paths.data / 'proxy-selections.json')
        self.last_traffic = {"running": False, "session": "", "upload": 0, "download": 0, "connections": 0}
        self.traffic_raw = {"upload": 0, "download": 0}
        self.traffic_offset = {"upload": 0, "download": 0}
        self.version_cache = (None, "")
        self.job = self.platform.job()
        self.active = None
        self.last_composed = None
        self.active_row = None
        self.events = deque(maxlen=80)
        self.log_handle = None
        self.routing_path = self.paths.data / 'routing-mode.json'
        try:
            mode = json.loads(self.routing_path.read_text(encoding='utf-8')).get('mode')
        except (OSError, ValueError, AttributeError):
            mode = 'rule'
        self.routing_mode = mode if mode in ('rule', 'global', 'direct') else 'rule'
        try:
            copied = seed_databases(self.resource_home, self.directory)
            if copied:
                self.event("已从内置资源初始化规则数据库，无需下载")
        except (OSError, ValueError, KeyError, TypeError):
            self.event("内置规则数据库初始化未完成，请检查资源完整性及目录权限")
        # Restore this app's leftover WinINET settings after an abnormal exit.
        if self.proxy.path.exists():
            result = self.proxy.restore()
            self.event("检测到上次代理备份：" + ("已恢复" if result["restored"] else result["reason"]))

    def event(self, message):
        self.events.append({"time": time.strftime("%H:%M:%S"), "message": message})

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def request(self, method, path, **kwargs):
        if not self.alive():
            raise HTTPException(409, "内核未运行，请先应用配置并启动")
        try:
            with httpx.Client(trust_env=False, timeout=kwargs.pop("timeout", 8),
                              headers={"Authorization": f"Bearer {self.secret}"}) as client:
                response = client.request(method, f"http://127.0.0.1:{self.controller_port}{path}", **kwargs)
                response.raise_for_status()
                return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "内核请求失败，操作未确认成功；请检查配置和内核状态") from None

    def status(self):
        with self.lock:
            routing_mode = self.routing_mode
            if self.alive():
                try:
                    routing_mode = self.request('GET', '/configs').get('mode')
                except HTTPException:
                    routing_mode = None
            return {"running": self.alive(), "installed": self.binary.exists(),
                    "routing_mode": routing_mode,
                    "active": self.active if self.alive() else None, "core_version": self.core_version(),
                    "proxy": self.proxy.status(), "events": list(self.events),
                    "tun": {"supported": self.platform.info['capabilities']['tun'], "admin": is_admin() or self.elevation.ready, "helper": self.platform.info['os'] == 'windows' and self.elevation.ready,
                            "enabled": bool(self.alive() and self.active and self.active.get("tun")),
                            "stack": (self.active or {}).get("tun_stack", "mixed"), "device": "ClashStudio",
                            "driver_installed": (self.binary.parent / "wintun.dll").exists(),
                            "conflicts": other_cores(self.process.pid if self.alive() else None)}}

    def change_routing_mode(self, mode):
        if mode not in ('rule', 'global', 'direct'):
            raise HTTPException(422, '代理模式无效')
        with self.lock:
            running = self.alive()
            old_mode = self.request('GET', '/configs').get('mode') if running else self.routing_mode
            active_path = self.directory / 'active.yaml'
            previous = active_path.read_text(encoding='utf-8') if active_path.exists() else None
            if running:
                self.request('PATCH', '/configs', json={'mode': mode})
                if self.request('GET', '/configs').get('mode') != mode:
                    raise HTTPException(502, '代理模式切换未确认，请刷新状态')
            try:
                if running and previous is not None:
                    config = parse_config(previous)
                    config['mode'] = mode
                    temporary = active_path.with_suffix('.tmp')
                    temporary.write_text(dump_config(config), encoding='utf-8')
                    temporary.replace(active_path)
                temporary = self.routing_path.with_suffix('.tmp')
                temporary.write_text(json.dumps({'mode': mode}), encoding='utf-8')
                temporary.replace(self.routing_path)
            except OSError:
                if running:
                    self.request('PATCH', '/configs', json={'mode': old_mode})
                    if previous is not None:
                        active_path.write_text(previous, encoding='utf-8')
                raise HTTPException(503, '代理模式保存失败，请检查目录权限') from None
            self.routing_mode = mode
            self.event('代理模式：' + mode)
            return self.status()

    def core_version(self):
        with self.lock:
            return self.read_core_version()

    def read_core_version(self):
        if not self.binary.exists():
            return "未安装"
        stamp = self.binary.stat().st_mtime_ns
        if self.version_cache[0] != stamp:
            try:
                result = subprocess.run([str(self.binary), "-v"], capture_output=True, timeout=3,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                version = result.stdout.decode("utf-8", errors="replace").splitlines()[0][:180]
                self.version_cache = (stamp, version if result.returncode == 0 else "读取失败")
            except (OSError, subprocess.TimeoutExpired, IndexError):
                self.version_cache = (stamp, "读取失败")
        return self.version_cache[1]

    def traffic(self):
        with self.lock:
            if self.alive():
                counters = self.request("GET", "/connections", timeout=2)
                for direction in ("upload", "download"):
                    raw = max(0, int(counters.get(direction + "Total", 0)))
                    if raw < self.traffic_raw[direction]:
                        self.traffic_offset[direction] += self.traffic_raw[direction]
                    self.traffic_raw[direction] = raw
                self.last_traffic = {"running": True, "session": str(self.process.pid),
                                     "upload": self.traffic_offset["upload"] + self.traffic_raw["upload"],
                                     "download": self.traffic_offset["download"] + self.traffic_raw["download"],
                                     "connections": len(counters.get("connections") or [])}
            else:
                self.last_traffic = {**self.last_traffic, "running": False, "connections": 0}
            return dict(self.last_traffic)

    def prepare(self, composed, port, tun=False, tun_stack="mixed"):
        config = dict(composed["config"])
        preferences = self.settings.load()
        # The alpha owns its listeners; imported profiles cannot bind LAN ports,
        # enable TUN, or expose a second controller behind the user's back.
        for key in ("port", "socks-port", "redir-port", "tproxy-port", "listeners", "iptables",
                    "external-controller-tls", "external-controller-pipe", "external-controller-unix",
                    "external-ui", "external-ui-url", "external-ui-name", "external-controller-cors",
                    "authentication", "skip-auth-prefixes", "lan-allowed-ips", "lan-disallowed-ips", "interface-name", "routing-mark"):
            config.pop(key, None)
        dns = preferences.dns_override.config() if preferences.dns_override.enabled else dict(config.get("dns", {}))
        dns.pop("listen", None)
        dns["ipv6"] = preferences.ipv6
        config["dns"] = dns
        config.update({"mixed-port": port, "bind-address": "*" if preferences.allow_lan else "127.0.0.1", "allow-lan": preferences.allow_lan,
                       "geo-auto-update": False,
                       "ipv6": preferences.ipv6,
                       "mode": self.routing_mode, "find-process-mode": "always", "tun": {"enable": False},
                       "external-controller": f"127.0.0.1:{self.controller_port}", "secret": self.secret})
        if self.platform.info['os'] == 'linux':
            profile = dict(config.get('profile') or {})
            profile.update({'store-selected': True, 'store-fake-ip': True})
            config['profile'] = profile
        if preferences.allow_lan:
            if preferences.lan_auth:
                config["authentication"] = [f"{preferences.lan_username}:{preferences.lan_password}"]
                config["skip-auth-prefixes"] = ["127.0.0.0/8", "::1/128"]
            config["lan-allowed-ips"] = ["127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7", "fe80::/10"]
            if preferences.ipv6:
                config["lan-allowed-ips"] += lan_ipv6_networks()
        if tun:
            config["tun"] = {"enable": True, "device": "ClashStudio", "stack": tun_stack,
                             "auto-route": True, "strict-route": True, "auto-detect-interface": True,
                             "dns-hijack": ["any:53", "tcp://any:53"]}
            if self.platform.info['os'] == 'linux':
                config['tun']['auto-redirect'] = True
            dns = config.setdefault("dns", {})
            dns["enable"] = True
            dns.setdefault("enhanced-mode", "fake-ip")
            dns.setdefault("fake-ip-range", "198.18.0.1/16")
            dns.setdefault("nameserver", ["https://dns.alidns.com/dns-query", "https://1.1.1.1/dns-query"])
            if self.platform.info['os'] == 'linux':
                # Keep our mapping separate from common upstream router Fake-IP
                # pools. Recover HTTP/TLS names when the upstream supplied an IP.
                dns['fake-ip-range'] = '198.19.0.1/16'
                # Resolve node hosts before a proxy is available. Subscription
                # fallback resolvers may themselves require that proxy.
                if not dns.get('proxy-server-nameserver'):
                    dns['proxy-server-nameserver'] = ['https://dns.alidns.com/dns-query', 'https://doh.pub/dns-query']
                sniffer = copy.deepcopy(config.get('sniffer') or {})
                sniffer.update({'enable': True, 'parse-pure-ip': True, 'force-dns-mapping': True})
                sniff = sniffer.setdefault('sniff', {})
                for protocol, ports in [('TLS', [443]), ('HTTP', [80, 8080]), ('QUIC', [443])]:
                    item = sniff.setdefault(protocol, {})
                    item.setdefault('ports', ports)
                    item['override-destination'] = True
                config['sniffer'] = sniffer
        return dump_config(config)

    def verify_tun(self, expected):
        # The REST controller becomes ready before Linux's TUN listener finishes.
        deadline = time.monotonic() + 5
        missing_interface = False
        while True:
            actual = self.request("GET", "/configs").get("tun", {}).get("enable", False)
            matched = bool(actual) == expected
            missing_interface = False
            if matched and expected and self.platform.info['os'] == 'linux':
                try:
                    socket.if_nametoindex('ClashStudio')
                except OSError:
                    missing_interface = True
            if matched and not missing_interface:
                return
            if time.monotonic() >= deadline:
                break
            time.sleep(.1)
        if missing_interface:
            raise HTTPException(502, 'Linux TUN 网卡未创建，请检查内核权限与运行日志')
        raise HTTPException(502, "内核返回的 TUN 状态与请求不一致，未确认配置生效")

    def restore_selectors(self, choices):
        if not choices:
            return
        catalog = self.request('GET', '/proxies').get('proxies', {})
        for name, selected in choices.items():
            group = catalog.get(name, {})
            if group.get('type') == 'Selector' and selected in group.get('all', []):
                self.request('PUT', '/proxies/' + quote(name, safe=''), json={'name': selected})

    def apply(self, composed, row, port, tun=False, tun_stack="mixed"):
        if tun:
            self.platform.require('tun')
        with self.lock:
            if tun:
                conflicts = other_cores(self.process.pid if self.alive() else None)
                if conflicts:
                    raise HTTPException(409, "检测到其他代理内核，请先在对应软件中关闭内核后再启用 TUN：" + "、".join(conflicts))
                if self.platform.info['os'] == 'windows' and not (self.binary.parent / "wintun.dll").exists():
                    raise HTTPException(503, "缺少 Wintun 驱动库，请补齐 bin/wintun.dll")
            if composed["errors"]:
                raise HTTPException(422, {"message": "模块配置未通过校验", "errors": composed["errors"]})
            if not row["enabled"]:
                raise HTTPException(422, "订阅已停用，请先在订阅编辑器中启用")
            if not self.binary.exists():
                raise HTTPException(503, "缺少随附的 Mihomo 内核")
            running = self.alive()
            linux = self.platform.info['os'] == 'linux'
            migrating = bool(tun and running and (
                (linux and not self.active.get('tun')) or
                (not linux and not is_admin() and not isinstance(self.process, ElevatedProcess))))
            rollback = None
            choices = self.selections.get(row['id'])
            if running and self.active["mixed_port"] != port:
                raise HTTPException(409, "修改代理端口需要先停止内核")
            if not running:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 0))
                    self.controller_port = probe.getsockname()[1]
                with socket.socket() as probe:
                    try:
                        if not running:
                            if os.name != "nt":
                                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            probe.bind(("127.0.0.1", port))
                    except OSError:
                        raise HTTPException(409, f"代理端口 {port} 已被占用，请修改端口") from None
            payload = self.prepare(composed, port, tun, tun_stack)
            candidate = self.directory / f"candidate-{secrets.token_hex(5)}.yaml"
            candidate.write_text(payload, encoding="utf-8")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                try:
                    copied = seed_databases(self.resource_home, self.directory)
                except (OSError, ValueError, KeyError, TypeError):
                    raise HTTPException(503, "本地规则数据库补齐失败，请检查 bin/geodata/source.json、数据库摘要及目录写入权限") from None
                if copied:
                    self.event("已从随附文件补齐规则数据库：" + "、".join(copied))
                with (self.directory / "validation.log").open("wb") as log:
                    check = subprocess.run([str(self.binary), "-t", "-d", str(self.directory), "-f", str(candidate)],
                                           stdout=log, stderr=subprocess.STDOUT, timeout=90, creationflags=flags)
                if check.returncode:
                    raise HTTPException(422, validation_message(self.directory / "validation.log", running))
                if tun and not is_admin():
                    self.elevation.ensure()
                if migrating:
                    if linux and self.active['profile_id'] == row['id']:
                        choices.update({name: item['now'] for name, item in self.request('GET', '/proxies').get('proxies', {}).items()
                                        if item.get('type') == 'Selector' and item.get('now')})
                    rollback = (copy.deepcopy(self.last_composed), dict(self.active_row), self.active["mixed_port"], bool(self.proxy.status().get("owned")))
                    self.stop()
                    running = False
                if running:
                    try:
                        self.request("PUT", "/configs?force=true", json={"path": str(candidate)}, timeout=40)
                        self.verify_tun(tun)
                    except HTTPException:
                        try:
                            self.request("PUT", "/configs?force=true", json={"path": str(self.directory / "active.yaml")}, timeout=40)
                        except HTTPException:
                            self.stop()
                            raise HTTPException(502, "新配置应用失败且旧配置恢复失败，已停止内核并尝试恢复系统代理") from None
                        raise HTTPException(502, "新配置应用失败，已重新加载上次运行配置") from None
                else:
                    if tun and not is_admin() and not linux:
                        self.process = self.elevation.launch(candidate)
                    else:
                        self.log_handle = (self.directory / "core.log").open("ab")
                        command = [str(self.binary), "-d", str(self.directory), "-f", str(candidate)]
                        if linux:
                            command = [sys.executable, '-I', '-B', str(Path(__file__).with_name('linux_core.py')),
                                       str(os.getpid()), str(self.binary), str(self.directory), str(candidate)]
                        self.process = subprocess.Popen(command,
                                                        stdout=self.log_handle, stderr=subprocess.STDOUT, creationflags=flags)
                        self.job.assign(self.process)
                    self.last_traffic = {"running": True, "session": str(self.process.pid), "upload": 0, "download": 0, "connections": 0}
                    self.traffic_raw = {"upload": 0, "download": 0}
                    self.traffic_offset = {"upload": 0, "download": 0}
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        if not self.alive():
                            break
                        try:
                            self.request("GET", "/version", timeout=0.4)
                            break
                        except HTTPException:
                            time.sleep(0.15)
                    else:
                        self.stop()
                        raise HTTPException(502, "内核启动超时，已停止；详情见 data/runtime/core.log")
                    if not self.alive():
                        raise HTTPException(502, "内核启动失败；详情见 data/runtime/core.log")
                    try:
                        self.verify_tun(tun)
                    except HTTPException:
                        self.stop()
                        raise
                    threading.Thread(target=self.monitor, args=(self.process,), daemon=True).start()
                self.restore_selectors(choices)
                active_path = self.directory / "active.yaml"
                active_path.write_text(payload, encoding="utf-8")
                self.active = {"profile_id": row["id"], "title": row["title"], "revision": row["revision"],
                               "workspace_revision": composed["workspace_revision"], "mixed_port": port,
                               "hash": hashlib.sha256(payload.encode()).hexdigest()[:12], "tun": tun, "tun_stack": tun_stack}
                self.last_composed = copy.deepcopy(composed)
                self.active_row = dict(row)
                self.event(f"已应用「{row['title']}」v{row['revision']} · 模块版本 {composed['workspace_revision']}")
                return self.status()
            except subprocess.TimeoutExpired:
                raise HTTPException(504, "内核配置校验超时；旧配置已保留") from None
            except BaseException:
                if rollback:
                    try:
                        self.stop()
                        self.apply(rollback[0], rollback[1], rollback[2], False, tun_stack)
                        self.restore_selectors(choices)
                        if rollback[3]:
                            self.proxy.enable(rollback[2])
                        self.event("TUN 迁移失败，已恢复普通权限内核")
                    except BaseException:
                        self.event("TUN 迁移失败；旧内核恢复未确认，请检查网络状态")
                raise
            finally:
                # The running core may still reference the initial config path;
                # keep only a bounded history of candidate files.
                candidates = sorted(self.directory.glob("candidate-*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
                for stale in candidates[12:]:
                    stale.unlink(missing_ok=True)

    def change_tun(self, enabled, stack):
        with self.lock:
            if not self.alive() or self.active is None or self.last_composed is None:
                raise HTTPException(409, "请先选择配置并启动内核，再切换 TUN")
            return self.apply(self.last_composed, self.active_row, self.active["mixed_port"], enabled, stack)

    def change_mode(self, mode, stack="mixed"):
        if mode == 'tun':
            self.platform.require('tun')
        elif mode == 'system':
            self.platform.require('system_proxy')
        with self.lock:
            if not self.alive() or self.active is None:
                raise HTTPException(409, "请先启动内核，再切换接管模式")
            old_tun = bool(self.active.get("tun"))
            old_stack = self.active.get("tun_stack", "mixed")
            if old_tun != (mode == "tun") or (mode == "tun" and old_stack != stack):
                self.change_tun(mode == "tun", stack)
            try:
                if mode == "system":
                    self.proxy.enable(self.active["mixed_port"])
                else:
                    restored = self.proxy.restore()
                    if self.proxy.path.exists() and not restored["restored"]:
                        raise ValueError(restored["reason"])
            except (OSError, ValueError) as error:
                if old_tun != bool((self.active or {}).get("tun")):
                    try:
                        self.change_tun(old_tun, old_stack)
                    except HTTPException:
                        self.stop()
                raise HTTPException(409, "接管模式切换未完成，请检查系统代理恢复状态与目录权限") from error
            self.event("接管模式已切换：" + {"system": "系统代理", "tun": "TUN", "manual": "仅代理端口"}[mode])
            return self.status()

    def monitor(self, process):
        process.wait()
        with self.lock:
            if self.process is process:
                self.proxy.restore()
                self.event("内核已退出；已尝试恢复由本程序设置的系统代理")
                if self.log_handle:
                    self.log_handle.close()
                    self.log_handle = None

    def stop(self, final_sample=True, report=True):
        with self.lock:
            if self.alive():
                try:
                    if final_sample:
                        self.traffic()
                except HTTPException:
                    pass
                try:
                    if self.active and self.active.get('tun'):
                        self.request("PATCH", "/configs", json={"tun": {"enable": False}}, timeout=1)
                except HTTPException:
                    self.event("内核未确认关闭 TUN；进程退出后请检查网络恢复状态")
            self.proxy.restore()
            if self.alive():
                self.process.terminate()
                try:
                    self.process.wait(timeout=6 if self.platform.info['os'] == 'linux' else 1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
                self.event("内核已停止")
            self.active = None
            self.last_traffic = {**self.last_traffic, "running": False, "connections": 0}
            if self.log_handle:
                self.log_handle.close()
                self.log_handle = None
            return self.status() if report else None
