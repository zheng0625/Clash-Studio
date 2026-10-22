from pathlib import Path
import ipaddress
import json
import secrets
import socket
import os
import subprocess
import threading
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from .modules import Strict


class DNSOverride(Strict):
    enabled: bool = False
    mode: Literal["fake-ip", "redir-host"] = "fake-ip"
    nameserver: list[str] = Field(default_factory=lambda: ["https://dns.alidns.com/dns-query", "https://1.1.1.1/dns-query"], max_length=32)
    fallback: list[str] = Field(default_factory=list, max_length=32)
    bootstrap: list[str] = Field(default_factory=lambda: ["223.5.5.5", "1.1.1.1"], max_length=16)
    proxy_nameserver: list[str] = Field(default_factory=list, max_length=32)
    fake_ip_filter: list[str] = Field(default_factory=lambda: ["*.lan", "*.local"], max_length=256)

    @field_validator("nameserver", "fallback", "proxy_nameserver", "bootstrap")
    @classmethod
    def resolvers(cls, values, info):
        result = []
        for raw in values:
            value = raw.strip()
            if not value or len(value) > 512 or any(c.isspace() for c in value):
                raise ValueError("DNS 地址不能为空、包含空白或超过 512 字符")
            try:
                ipaddress.ip_address(value)
            except ValueError:
                if info.field_name == "bootstrap":
                    raise ValueError("引导 DNS 请填写 IPv4 或 IPv6 地址") from None
                if value != "system":
                    try:
                        parsed = urlsplit(value if "://" in value else "//" + value)
                        if parsed.scheme and parsed.scheme not in ("https", "tls", "tcp", "udp", "quic", "h3"):
                            raise ValueError()
                        if not parsed.hostname or parsed.username or parsed.password:
                            raise ValueError()
                        if parsed.port is not None and not 1 <= parsed.port <= 65535:
                            raise ValueError()
                        if not parsed.scheme:
                            ipaddress.ip_address(parsed.hostname)
                    except ValueError:
                        raise ValueError("DNS 地址须为 IP、IP:端口或受支持的 DNS URL") from None
            if value not in result:
                result.append(value)
        return result

    @field_validator("fake_ip_filter")
    @classmethod
    def filters(cls, values):
        result = []
        for value in values:
            value = value.strip()
            if not value or len(value) > 253 or any(c.isspace() for c in value) or "://" in value or "," in value:
                raise ValueError("Fake-IP 排除项请填写域名或域名通配符")
            if value not in result:
                result.append(value)
        return result

    @model_validator(mode="after")
    def required_resolvers(self):
        if self.enabled and (not self.nameserver or not self.bootstrap):
            raise ValueError("开启 DNS 覆写时至少填写一个主 DNS 和一个引导 DNS")
        return self

    def config(self):
        result = {"enable": True, "enhanced-mode": self.mode, "nameserver": self.nameserver,
                  "default-nameserver": self.bootstrap, "respect-rules": False}
        if self.mode == "fake-ip":
            result.update({"fake-ip-range": "198.18.0.1/16", "fake-ip-filter-mode": "blacklist", "fake-ip-filter": self.fake_ip_filter})
        if self.fallback:
            result["fallback"] = self.fallback
        if self.proxy_nameserver:
            result["proxy-server-nameserver"] = self.proxy_nameserver
        return result


class ClientSettings(Strict):
    allow_lan: bool = False
    ipv6: bool = False
    lan_auth: bool = False
    mixed_port: int | None = Field(default=None, ge=1024, le=65535)
    dns_override: DNSOverride = Field(default_factory=DNSOverride)
    lan_username: str = Field(default="clashstudio", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    lan_password: str = Field(default_factory=lambda: secrets.token_urlsafe(18), max_length=128)

    @model_validator(mode="before")
    @classmethod
    def preserve_existing_auth(cls, value):
        # Existing installations with LAN enabled previously required authentication.
        if isinstance(value, dict) and "lan_auth" not in value and value.get("allow_lan") and value.get("lan_password"):
            return {**value, "lan_auth": True}
        return value

    @model_validator(mode="after")
    def authentication_fields(self):
        if self.lan_auth and (not self.lan_username or len(self.lan_password) < 8):
            raise ValueError("开启代理认证时需填写用户名及至少 8 位密码")
        return self

    @field_validator("lan_password")
    @classmethod
    def password(cls, value):
        if any(ord(c) < 32 or c == ":" for c in value):
            raise ValueError("密码不能包含控制字符或冒号")
        return value


class SettingsStore:
    def __init__(self, path: Path):
        self.path, self.lock = path, threading.RLock()
        if not path.exists():
            self.save(ClientSettings())

    def load(self):
        with self.lock:
            return ClientSettings.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, value: ClientSettings):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.path)
            return value


def lan_addresses():
    result = []
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None):
            address = item[4][0]
            ip = ipaddress.ip_address(address.split("%")[0])
            if not ip.is_loopback and not ip.is_link_local and not ip.is_unspecified and not (ip.version == 4 and ip in ipaddress.ip_network("198.18.0.0/15")):
                if address not in result:
                    result.append(address)
    except OSError:
        pass
    return result


def lan_ipv6_networks():
    """Allow actual NIC prefixes rather than opening global IPv6 to everyone."""
    if os.name != "nt":
        return []
    try:
        command = "@(Get-NetIPAddress -AddressFamily IPv6 -AddressState Preferred -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceAlias -ne 'ClashStudio' } | Select-Object IPAddress,PrefixLength) | ConvertTo-Json -Compress"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True,
                                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        values = json.loads(result.stdout.decode("utf-8-sig")) if result.stdout.strip() else []
        if isinstance(values, dict):
            values = [values]
        networks = []
        for value in values:
            ip = ipaddress.ip_address(value["IPAddress"])
            length = int(value["PrefixLength"])
            if ip.is_global and 32 <= length <= 128:
                networks.append(str(ipaddress.ip_network(f"{ip}/{length}", strict=False)))
        return list(dict.fromkeys(networks))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return []
