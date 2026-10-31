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
from .dns_protection import protect_dns
from .selections import SelectionStore
from .atomic import atomic_text
from .operations import operation_id, cancelled
from .logs import ProcessLog


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
        self.lifecycle_lock = threading.RLock()
        self.client_lock = threading.RLock()
        self.version_lock = threading.Lock()
        self.sample_lock = threading.RLock()
        self._http = None
        self._cancel = threading.Event()
        self._cancel_epoch = 0
        self.operation = None
        self.egress_version = 0
        self._choices_signature = None
        self._connection_sample = None
        self._connection_at = 0.0
        self._connection_session = None
        self._connection_wire = None
        self.conflicts_cache = []
        self._status_lock_wait = deque(maxlen=256)
        self.proxy = self.platform.proxy()
        self._proxy_cache = None
        self._proxy_cache_at = 0
        self._proxy_refreshing = False
        self._proxy_sequence = 0
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
        process = self.process
        return process is not None and process.poll() is None

    def invalidate_egress(self):
        with self.lock:
            self.egress_version += 1

    def proxies(self):
        value = self.request('GET', '/proxies')
        signature = tuple(sorted((name, item.get('now')) for name, item in value.get('proxies', {}).items() if item.get('all') is not None))
        with self.lock:
            if self._choices_signature is not None and signature != self._choices_signature:
                self.egress_version += 1
            self._choices_signature = signature
        return value

    def egress_identity(self, observe=True):
        if observe and self.alive():
            self.proxies()
        with self.lock:
            process = self.process
            return (process.pid if process is not None and process.poll() is None else 0, (self.active or {}).get('hash'), self.routing_mode, self.egress_version)

    def request_cancel(self, key=None):
        with self.lock:
            if key is not None and (not self.operation or self.operation['operation_id'] != key or self.operation['phase'] in ('succeeded', 'failed', 'cancelled')):
                return
            self._cancel_epoch += 1
            self._cancel.set()

    def _check_cancel(self):
        cancellation = cancelled.get()
        if self._cancel.is_set() or (cancellation and cancellation()):
            raise HTTPException(409, '操作已取消，未提交新配置')

    def _phase(self, phase):
        with self.lock:
            if self.operation:
                now = time.time()
                timings = dict(self.operation.get('phase_ms', {}))
                previous = self.operation['phase']
                timings[previous] = timings.get(previous, 0) + round((now - self.operation.get('updated_at', self.operation['started_at'])) * 1000, 2)
                self.operation = {**self.operation, 'phase': phase, 'updated_at': now, 'phase_ms': timings}

    def _retire_client(self):
        with self.client_lock:
            session, self._http = self._http, None
            if session:
                session['retired'] = True
                if not session['users']:
                    session['client'].close()

    def request(self, method, path, **kwargs):
        process = self.process
        if process is None or process.poll() is not None:
            raise HTTPException(409, '内核未运行，请先应用配置并启动')
        key = (process, self.controller_port, self.secret)
        with self.client_lock:
            if not self._http or self._http['key'] != key:
                self._retire_client()
                self._http = dict(key=key, users=0, retired=False, client=httpx.Client(
                    trust_env=False, timeout=8, limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
                    headers={'Authorization': f'Bearer {self.secret}'}))
            session = self._http
            session['users'] += 1
        try:
            response = session['client'].request(method, f'http://127.0.0.1:{key[1]}{path}', **kwargs)
            response.raise_for_status()
            value = response.json() if response.content else {}
            if self.process is not process or process.poll() is not None or session['retired']:
                raise HTTPException(409, '内核会话已改变，请重试')
            return value
        except (httpx.HTTPError, ValueError, RuntimeError):
            raise HTTPException(502, '内核请求失败，操作未确认成功；请检查配置和内核状态') from None
        finally:
            with self.client_lock:
                session['users'] -= 1
                if session['retired'] and not session['users']:
                    session['client'].close()

    def refresh_proxy_status(self):
        with self.lock:
            self._proxy_sequence += 1
            sequence = self._proxy_sequence
        try:
            value = {**self.proxy.status(), 'sampled_at': time.time(), 'confirmed': True}
            with self.lock:
                if sequence == self._proxy_sequence:
                    self._proxy_cache, self._proxy_cache_at = value, time.monotonic()
        except (OSError, ValueError):
            with self.lock:
                if sequence == self._proxy_sequence and self._proxy_cache:
                    self._proxy_cache = {**self._proxy_cache, 'confirmed': False}
        finally:
            with self.lock:
                if sequence == self._proxy_sequence:
                    self._proxy_refreshing = False

    def proxy_snapshot(self):
        with self.lock:
            value = dict(self._proxy_cache or {'supported': self.platform.info['capabilities']['system_proxy'], 'owned': False, 'enabled': False, 'server': '', 'confirmed': False})
            value['stale'] = time.monotonic() - self._proxy_cache_at > 5
            if value['stale'] and not self._proxy_refreshing:
                self._proxy_refreshing = True
                threading.Thread(target=self.refresh_proxy_status, daemon=True, name='proxy-status').start()
            return value

    def status(self):
        # No validation, native waits, process scans or HTTP requests on the status path.
        started = time.perf_counter()
        with self.lock:
            self._status_lock_wait.append((time.perf_counter() - started) * 1000)
            process = self.process
            running = process is not None and process.poll() is None
            active = copy.deepcopy(self.active) if running else None
            operation = copy.deepcopy(self.operation)
            events = list(self.events)
            mode, egress = self.routing_mode, self.egress_version
        return {'running': running, 'installed': self.binary.exists(), 'routing_mode': mode,
                'active': active, 'core_version': self.version_cache[1] or '读取中…',
                'proxy': self.proxy_snapshot(), 'events': events, 'operation': operation,
                'sampled_at': time.time(), 'session': str(process.pid) if running else '', 'egress_version': egress,
                'tun': {'supported': self.platform.info['capabilities']['tun'], 'admin': is_admin() or self.elevation.ready,
                        'helper': self.platform.info['os'] == 'windows' and self.elevation.ready,
                        'enabled': bool(active and active.get('tun')), 'stack': (active or {}).get('tun_stack', 'mixed'),
                        'device': 'ClashStudio', 'driver_installed': (self.binary.parent / 'wintun.dll').exists(),
                        'conflicts': list(self.conflicts_cache)}}

    @staticmethod
    def _sample_result(value, summary=False):
        if summary:
            return {key: value.get(key) for key in ('uploadTotal', 'downloadTotal', 'sampled_at', 'session', 'stale')} | {'connection_count': len(value.get('connections') or [])}
        return copy.deepcopy(value)

    def connection_snapshot(self, force=False, summary=False):
        with self.sample_lock:
            process = self.process
            if not self.alive():
                return {'connections': [], 'uploadTotal': 0, 'downloadTotal': 0, 'session': '', 'sampled_at': time.time(), 'stale': False}
            if not force and self._connection_session is process and self._connection_sample is not None and time.monotonic() - self._connection_at < .9:
                return self._sample_result(self._connection_sample, summary)
            value = self.request('GET', '/connections', timeout=2)
            if self.process is not process or not self.alive():
                raise HTTPException(409, '连接采样所属会话已结束')
            value.update(session=str(process.pid), sampled_at=time.time(), stale=False)
            # The request result is owned by this cache; callers only ever
            # receive copies, so the second full deepcopy is unnecessary.
            self._connection_sample, self._connection_session, self._connection_at = value, process, time.monotonic()
            return self._sample_result(value, summary)

    def connection_json(self):
        # The HTTP endpoint reuses immutable encoded bytes, avoiding repeated
        # deep copies and JSON encoding of a large connection list.
        with self.sample_lock:
            summary = self.connection_snapshot(summary=True)
            if not self.alive() or self._connection_sample is None:
                self._clear_connection_cache_locked()
                return json.dumps(summary | {'connections': []}).encode()
            key = (self._connection_session, self._connection_at)
            if self._connection_wire is None or self._connection_wire[0] != key:
                self._connection_wire = (key, json.dumps(self._connection_sample, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            return self._connection_wire[1]

    def invalidate_connections(self):
        # Lifecycle paths hold lifecycle_lock; lifecycle_lock -> sample_lock is
        # the only order used, matching stop/apply/traffic.
        with self.sample_lock:
            self._clear_connection_cache_locked()

    def _clear_connection_cache_locked(self):
        self._connection_sample = None
        self._connection_session = None
        self._connection_at = 0.0
        self._connection_wire = None

    def change_routing_mode(self, mode):
        if mode not in ('rule', 'global', 'direct'):
            raise HTTPException(422, '代理模式无效')
        with self.lifecycle_lock:
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
            self.invalidate_egress()
            self.event('代理模式：' + mode)
            return self.status()

    def core_version(self):
        with self.version_lock:
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
        with self.sample_lock:
            if self.alive():
                counters = self.connection_snapshot(summary=True)
                for direction in ("upload", "download"):
                    raw = max(0, int(counters.get(direction + "Total") or 0))
                    if raw < self.traffic_raw[direction]:
                        self.traffic_offset[direction] += self.traffic_raw[direction]
                    self.traffic_raw[direction] = raw
                self.last_traffic = {"running": True, "session": counters["session"],
                                     "upload": self.traffic_offset["upload"] + self.traffic_raw["upload"],
                                     "download": self.traffic_offset["download"] + self.traffic_raw["download"],
                                     "connections": counters["connection_count"], "sampled_at": counters["sampled_at"], "stale": False}
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
        if preferences.dns_leak_prevention:
            protect_dns(config, dns)
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
                             "auto-route": True, "strict-route": bool(preferences.tun_strict_route), "auto-detect-interface": True,
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
                self._check_cancel()
                self.request('PUT', '/proxies/' + quote(name, safe=''), json={'name': selected})
                actual = self.request('GET', '/proxies').get('proxies', {}).get(name, {})
                if actual.get('now') != selected:
                    raise HTTPException(502, '节点恢复未确认')

    def validate_candidate(self, candidate, flags, running):
        with (self.directory / 'validation.log').open('wb') as log:
            process = subprocess.Popen([str(self.binary), '-t', '-d', str(self.directory), '-f', str(candidate)],
                                       stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            try:
                deadline = time.monotonic() + 90
                while process.poll() is None:
                    self._check_cancel()
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired('validation', 90)
                    time.sleep(.05)
                if process.returncode:
                    raise HTTPException(422, validation_message(self.directory / 'validation.log', running))
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()

    def apply(self, composed, row, port, tun=False, tun_stack='mixed', validator=None, capture_mode=None, expected_epoch=None):
        with self.lock:
            epoch = self._cancel_epoch if expected_epoch is None else expected_epoch
        with self.lifecycle_lock:
            with self.lock:
                if epoch != self._cancel_epoch:
                    raise HTTPException(409, {'code': 'OPERATION_CANCELLED', 'message': '排队中的应用已被停止请求取消'})
                cancellation = cancelled.get()
                if cancellation and cancellation():
                    raise HTTPException(409, {'code': 'OPERATION_CANCELLED', 'message': '应用已取消'})
                self._cancel.clear()
            key = operation_id.get() or secrets.token_hex(12)
            self.operation = dict(operation_id=key, phase='preparing', started_at=time.time(), profile_revision=row.get('revision'), workspace_revision=composed.get('workspace_revision'))
            try:
                result = self._apply_impl(composed, row, port, tun, tun_stack, validator, capture_mode)
                self._phase('succeeded')
                return self.status()
            except BaseException:
                self._phase('cancelled' if self._cancel.is_set() else 'failed')
                raise

    def _apply_impl(self, composed, row, port, tun=False, tun_stack="mixed", validator=None, capture_mode=None, payload_override=None):
        if tun:
            self.platform.require('tun')
        with self.lifecycle_lock:
            if tun:
                conflicts = other_cores(self.process.pid if self.alive() else None)
                self.conflicts_cache = conflicts
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
            original_running, original_process = running, self.process
            old_active, old_row, old_composed = copy.deepcopy(self.active), copy.deepcopy(self.active_row), copy.deepcopy(self.last_composed)
            old_owned = bool(self.proxy.status().get('owned'))
            old_payload = (self.directory / 'active.yaml').read_text(encoding='utf-8') if running else None
            old_choices = {name: item['now'] for name, item in self.request('GET', '/proxies').get('proxies', {}).items()
                           if item.get('type') == 'Selector' and item.get('now')} if running else {}
            loaded = False
            rollback_path = self.directory / ('rollback-' + secrets.token_hex(6) + '.yaml')
            if running:
                atomic_text(rollback_path, old_payload)
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
                    self.controller_port = int(parse_config(payload_override)['external-controller'].rsplit(':', 1)[1]) if payload_override else probe.getsockname()[1]
                with socket.socket() as probe:
                    try:
                        if not running:
                            if os.name != "nt":
                                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            probe.bind(("127.0.0.1", port))
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                                udp.bind(("127.0.0.1", port))
                    except OSError:
                        raise HTTPException(409, f"代理端口 {port} 已被占用，请修改端口") from None
            payload = payload_override if payload_override is not None else self.prepare(composed, port, tun, tun_stack)
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
                self._phase('validating')
                self.validate_candidate(candidate, flags, running)
                self._check_cancel()
                if validator:
                    validator()
                if tun and not is_admin():
                    self.elevation.ensure()
                if migrating:
                    loaded = True
                    if linux and self.active['profile_id'] == row['id']:
                        choices.update({name: item['now'] for name, item in self.request('GET', '/proxies').get('proxies', {}).items()
                                        if item.get('type') == 'Selector' and item.get('now')})
                    rollback = (copy.deepcopy(self.last_composed), dict(self.active_row), self.active["mixed_port"], bool(self.proxy.status().get("owned")))
                    self._stop_locked()
                    running = False
                self._phase('loading')
                self._check_cancel()
                loaded = True
                if running:
                    self.request('PUT', '/configs?force=true', json={'path': str(candidate)}, timeout=40)
                    self.verify_tun(tun)
                else:
                    if tun and not is_admin() and not linux:
                        self.process = self.elevation.launch(candidate)
                    else:
                        self.log_handle = ProcessLog(self.directory / 'core.log', on_error=lambda: self.event('内核日志写入失败，已停止保存日志'))
                        command = [str(self.binary), "-d", str(self.directory), "-f", str(candidate)]
                        if linux:
                            command = [sys.executable, '-I', '-B', str(Path(__file__).with_name('linux_core.py')),
                                       str(os.getpid()), str(self.binary), str(self.directory), str(candidate)]
                        self.process = subprocess.Popen(command,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
                        self.log_handle.attach(getattr(self.process, 'stdout', None))
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
                            self._check_cancel()
                            time.sleep(0.15)
                    else:
                        self._stop_locked()
                        raise HTTPException(502, "内核启动超时，已停止；详情见 data/runtime/core.log")
                    if not self.alive():
                        raise HTTPException(502, "内核启动失败；详情见 data/runtime/core.log")
                    try:
                        deadline = time.monotonic() + 2
                        while True:
                            self._check_cancel()
                            try:
                                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                                    break
                            except OSError:
                                if time.monotonic() >= deadline:
                                    raise HTTPException(502, '内核未建立代理监听，已停止') from None
                                time.sleep(.05)
                        self.verify_tun(tun)
                    except HTTPException:
                        self._stop_locked()
                        raise
                    threading.Thread(target=self.monitor, args=(self.process,), daemon=True).start()
                self._check_cancel()
                self._phase('restoring-selectors')
                self.restore_selectors(choices)
                self._check_cancel()
                if validator:
                    validator()
                if capture_mode is not None:
                    self._phase('capture')
                    if capture_mode == 'system':
                        self.platform.require('system_proxy')
                        self.proxy.enable(port)
                    else:
                        restored = self.proxy.restore()
                        if self.proxy.path.exists() and not restored['restored']:
                            raise ValueError('system proxy restoration unconfirmed')
                self._phase('persisting')
                active_path = self.directory / "active.yaml"
                atomic_text(active_path, payload)
                self._check_cancel()
                self.active = {"profile_id": row["id"], "title": row["title"], "revision": row["revision"],
                               "workspace_revision": composed["workspace_revision"], "mixed_port": port,
                               "hash": hashlib.sha256(payload.encode()).hexdigest()[:12], "tun": tun, "tun_stack": tun_stack}
                self.invalidate_egress()
                self.invalidate_connections()
                self.last_composed = copy.deepcopy(composed)
                self.active_row = dict(row)
                self.refresh_proxy_status()
                self.event(f"已应用「{row['title']}」v{row['revision']} · 模块版本 {composed['workspace_revision']}")
                return self.status()
            except subprocess.TimeoutExpired:
                raise HTTPException(504, "内核配置校验超时；旧配置已保留") from None
            except BaseException as error:
                if loaded:
                    restored = False
                    if original_running and not self._cancel.is_set():
                        self._phase('rolling-back')
                        try:
                            if self.process is original_process and self.alive():
                                self.request('PUT', '/configs?force=true', json={'path': str(rollback_path)}, timeout=40)
                                self.verify_tun(bool(old_active.get('tun')))
                                self.restore_selectors(old_choices)
                                configs = self.request('GET', '/configs')
                                if configs.get('mixed-port') != old_active['mixed_port']:
                                    raise ValueError('rollback listener mismatch')
                                self.active, self.active_row, self.last_composed = old_active, old_row, old_composed
                                atomic_text(self.directory / 'active.yaml', old_payload)
                            else:
                                self._stop_locked()
                                self._apply_impl(old_composed, old_row, old_active['mixed_port'], bool(old_active.get('tun')), old_active.get('tun_stack', 'mixed'), payload_override=old_payload)
                                self.restore_selectors(old_choices)
                            if old_owned:
                                self.proxy.enable(old_active['mixed_port'])
                            else:
                                self.proxy.restore()
                            self._check_cancel()
                            restored = True
                        except BaseException:
                            restored = False
                    if not restored:
                        self._stop_locked(final_sample=False, report=False)
                    with self.lock:
                        self.operation = {**self.operation, 'rollback': 'verified' if restored else 'stopped'}
                    self.event('配置应用失败：' + ('已核验并恢复旧配置' if restored else '恢复未确认，已停止内核并尝试恢复系统代理'))
                    raise HTTPException(409 if self._cancel.is_set() else 502,
                                        {'message': '配置应用失败，已核验恢复旧配置' if restored else '配置未提交，已停止内核并尝试恢复系统代理',
                                         'code': 'APPLY_CANCELLED' if self._cancel.is_set() else 'APPLY_ROLLED_BACK' if restored else 'APPLY_STOPPED',
                                         'retryable': True, 'operation_id': self.operation['operation_id'], 'rollback': 'verified' if restored else 'stopped'}) from error
                raise
            finally:
                # The running core may still reference the initial config path;
                # keep only a bounded history of candidate files.
                rollback_path.unlink(missing_ok=True)
                candidates = sorted(self.directory.glob("candidate-*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
                for stale in candidates[12:]:
                    stale.unlink(missing_ok=True)

    def change_tun(self, enabled, stack):
        with self.lifecycle_lock:
            if not self.alive() or self.active is None or self.last_composed is None:
                raise HTTPException(409, "请先选择配置并启动内核，再切换 TUN")
            return self.apply(self.last_composed, self.active_row, self.active["mixed_port"], enabled, stack)

    def change_mode(self, mode, stack="mixed"):
        if mode == 'tun':
            self.platform.require('tun')
        elif mode == 'system':
            self.platform.require('system_proxy')
        with self.lifecycle_lock:
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
                        self._stop_locked()
                raise HTTPException(409, "接管模式切换未完成，请检查系统代理恢复状态与目录权限") from error
            self.refresh_proxy_status()
            self.invalidate_egress()
            self.event("接管模式已切换：" + {"system": "系统代理", "tun": "TUN", "manual": "仅代理端口"}[mode])
            return self.status()

    def monitor(self, process):
        process.wait()
        with self.lifecycle_lock:
            if self.process is process:
                self._retire_client()
                self.invalidate_connections()
                self.invalidate_egress()
                self.proxy.restore()
                self.event("内核已退出；已尝试恢复由本程序设置的系统代理")
                if self.log_handle:
                    self.log_handle.close()
                    self.log_handle = None

    def stop(self, final_sample=True, report=True):
        self.request_cancel()
        with self.lifecycle_lock:
            self.operation = dict(operation_id=operation_id.get() or secrets.token_hex(12), phase='stopping', started_at=time.time())
            self._stop_locked(final_sample, False)
            self._phase('succeeded')
            if report:
                self.refresh_proxy_status()
            return self.status() if report else None

    def _stop_locked(self, final_sample=True, report=True):
        with self.lifecycle_lock:
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
            try:
                self.proxy.restore()
            except (OSError, ValueError):
                self.event('系统代理恢复失败，请检查系统代理状态；继续停止内核')
            if self.alive():
                self.process.terminate()
                try:
                    self.process.wait(timeout=6 if self.platform.info['os'] == 'linux' else 1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
                self.event("内核已停止")
            self._retire_client()
            self.process = None
            self.invalidate_connections()
            self.invalidate_egress()
            self.active = None
            self.last_traffic = {**self.last_traffic, "running": False, "connections": 0}
            if self.log_handle:
                self.log_handle.close()
                self.log_handle = None
            if report:
                self.refresh_proxy_status()
            return self.status() if report else None
