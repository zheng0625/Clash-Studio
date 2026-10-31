"""On-demand loopback-only core for measuring a published subscription."""
import copy
import hashlib
import json
import socket
import threading
from fastapi import HTTPException

from .runtime import Runtime
from .delay import DelayMonitor
from .settings import ClientSettings


def catalog(config):
    proxies = {p["name"]: {"name": p["name"], "type": p.get("type", "proxy")} for p in config.get("proxies", [])}
    proxies.update({n: {"name": n, "type": t} for n, t in [("DIRECT", "Direct"), ("REJECT", "Reject")]})
    mapping = {"select": "Selector", "url-test": "URLTest", "fallback": "Fallback", "load-balance": "LoadBalance"}
    for group in config.get("proxy-groups", []):
        members = list(group.get("proxies", []))
        if group.get("include-all") or group.get("include-all-proxies"):
            members += [p["name"] for p in config.get("proxies", [])]
        proxies[group["name"]] = {"name": group["name"], "type": mapping.get(group.get("type"), group.get("type", "Selector")),
                                   "all": list(dict.fromkeys(members))}
        if group.get('type') == 'select' and members:
            proxies[group['name']]['now'] = members[0]
    return {"proxies": proxies, "has_providers": bool(config.get("proxy-providers"))}


class ProbeManager:
    def __init__(self, main):
        self.main, self.lock = main, threading.RLock()
        self.core, self.key, self.timer = None, None, None
        self.active = 0
        self.epoch_lock = threading.Lock()
        self.epoch = 0

    def ticket(self):
        with self.epoch_lock:
            return self.epoch

    def cancel_pending(self):
        # Independent of the startup lock: stop can invalidate work even while
        # a slow core is validating or a request is waiting for self.lock.
        with self.epoch_lock:
            self.epoch += 1

    def check_ticket(self, ticket):
        if ticket != self.ticket():
            raise HTTPException(409, {'code': 'OPERATION_CANCELLED', 'message': '测速已停止，请重新发起测速'})

    def fingerprint(self, config):
        return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def ensure(self, config, ticket=None):
        ticket = self.ticket() if ticket is None else ticket
        with self.lock:
            self.check_ticket(ticket)
            key = self.fingerprint(config)
            if self.core and self.core.alive() and self.key == key:
                self.touch()
                return self.core
            self._stop_locked()
            core = Runtime(self.main.home, resource_home=self.main.resource_home, data_dir=self.main.paths.data / 'probe' / 'data')
            core.binary = self.main.binary
            preferences = self.main.settings.load()
            core.settings.save(ClientSettings(ipv6=preferences.ipv6, dns_override=preferences.dns_override))
            # No imported routes, listeners, controller, DNS listener or TUN.
            selected = {name: copy.deepcopy(config[name]) for name in ("proxies", "proxy-groups", "proxy-providers") if name in config}
            dns = config.get("dns", {})
            selected["dns"] = {name: copy.deepcopy(dns[name]) for name in ("nameserver", "default-nameserver", "proxy-server-nameserver", "direct-nameserver") if name in dns}
            selected["rules"] = ["MATCH,DIRECT"]
            for provider in selected.get("proxy-providers", {}).values():
                provider["health-check"] = {"enable": False}
                if provider.get("type") == "http":
                    provider["path"] = str(core.directory / "providers" / (hashlib.sha256(str(provider.get("url", "")).encode()).hexdigest() + ".yaml"))
            for group in selected.get("proxy-groups", []):
                if group.get("type") in ("url-test", "fallback", "load-balance"):
                    group["type"] = "select"
            with socket.socket() as address:
                address.bind(("127.0.0.1", 0))
                port = address.getsockname()[1]
            try:
                core.apply({"config": selected, "errors": [], "workspace_revision": 1},
                           {"id": "isolated-probe", "title": "独立节点测速", "enabled": True, "revision": 1}, port)
                self.check_ticket(ticket)
            except BaseException:
                try:
                    core.stop()
                finally:
                    core.job.close()
                raise
            self.core, self.key = core, key
            self.touch()
            return core

    def touch(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(120, self.idle_stop)
        self.timer.daemon = True
        self.timer.start()

    def idle_stop(self):
        with self.lock:
            if self.active:
                self.touch()
            else:
                self.stop()

    def stop(self):
        self.cancel_pending()
        with self.lock:
            self._stop_locked()

    def _stop_locked(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.core:
            try:
                self.core.stop(final_sample=False, report=False)
            finally:
                self.core.job.close()
                self.core = None
        self.key = None

    def read_catalog(self, config):
        with self.lock:
            if self.core and self.core.alive() and self.key == self.fingerprint(config):
                proxies = self.core.request("GET", "/proxies").get("proxies", {})
                published = catalog(config)["proxies"]
                for name, value in proxies.items():
                    if name in published and published[name].get("all") is not None:
                        value["type"] = published[name]["type"]
                return {"proxies": proxies, "has_providers": bool(config.get("proxy-providers"))}
        return catalog(config)

    def measure(self, config, name, endpoint, timeout_ms, ticket=None):
        ticket = self.ticket() if ticket is None else ticket
        with self.lock:
            core = self.ensure(config, ticket)
            self.active += 1
            if not hasattr(core, "delay_monitor"):
                core.delay_monitor = DelayMonitor(core)
            delay = core.delay_monitor
        try:
            self.check_ticket(ticket)
            result = delay.probe(name, endpoint, timeout_ms)
            self.check_ticket(ticket)
            return result
        finally:
            with self.lock:
                self.active -= 1
                if self.core is core and ticket == self.ticket():
                    self.touch()
