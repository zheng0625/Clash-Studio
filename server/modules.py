from __future__ import annotations

import copy
import ipaddress
import json
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.engine import dump_config, parse_config, plain


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Match(Strict):
    kind: Literal["DOMAIN", "DOMAIN-SUFFIX", "PROCESS-NAME", "PROCESS-PATH", "IP-CIDR", "IP-CIDR6"]
    value: str = Field(min_length=1, max_length=1024)

    @field_validator("value")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(c in value for c in ",\r\n\x00"):
            raise ValueError("匹配值不能为空，且不能包含逗号、换行或空字符")
        return value


class Module(Strict):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=200)
    strict: bool = True
    matches: list[Match] = Field(min_length=1, max_length=500)


class Plan(Strict):
    module_ids: list[str] = Field(default_factory=list, max_length=100)
    default_target: str = Field(default="", max_length=200)


class Workspace(Strict):
    revision: int = Field(default=1, ge=1)
    modules: list[Module] = Field(default_factory=list, max_length=100)
    plans: dict[str, Plan] = Field(default_factory=dict, max_length=500)


class WorkspaceStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if self.path.exists():
                return Workspace.model_validate_json(self.path.read_text(encoding="utf-8"))
            return Workspace()

    def save(self, proposed: Workspace):
        with self.lock:
            current = self.load()
            if proposed.revision != current.revision:
                raise HTTPException(409, "模块配置已被其他窗口修改，请重新载入")
            ids = [m.id for m in proposed.modules]
            if len(ids) != len(set(ids)):
                raise HTTPException(422, "模块 ID 重复")
            for plan in proposed.plans.values():
                if len(plan.module_ids) != len(set(plan.module_ids)) or set(plan.module_ids) - set(ids):
                    raise HTTPException(422, "方案存在重复或缺失的模块引用")
            proposed.revision += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(proposed.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.path)
            return proposed


def compose(published: str, profile_id: str, workspace: Workspace):
    """Overlay ordered reusable modules on the last published Studio config."""
    config = copy.deepcopy(plain(parse_config(published)))
    plan = workspace.plans.get(profile_id, Plan())
    modules = {m.id: m for m in workspace.modules}
    groups = {g["name"]: g for g in config.get("proxy-groups", [])}
    proxies = {p["name"]: p for p in config.get("proxies", [])}
    valid = set(groups) | set(proxies) | {"DIRECT", "REJECT", "REJECT-DROP"}
    errors, warnings, rules, origins = [], [], [], []

    inspected = {}

    def inspect(target, visited=None):
        visited = set() if visited is None else visited
        if target in visited:
            return ["策略组循环引用"]
        if target in inspected:
            return list(inspected[target])
        if target in ("REJECT", "REJECT-DROP"):
            return []
        if target not in groups and target not in proxies:
            return [f"不允许的出口 {target}"]
        visited = visited | {target}
        if target in proxies:
            proxy = proxies[target]
            if proxy.get("type", "").lower() in ("direct", "dns"):
                return [f"节点 {target} 提供直连出口"]
            return inspect(proxy["dialer-proxy"], visited) if proxy.get("dialer-proxy") else []
        group = groups[target]
        if group.get("use") or any(group.get(k) for k in ("include-all", "include-all-providers", "include-all-proxies")):
            return [f"组 {target} 含动态成员，严格模式无法完整审查"]
        members = group.get("proxies", [])
        if not members:
            return [f"组 {target} 没有可审查的成员"]
        reasons = [reason for member in members for reason in inspect(member, visited)]
        if '策略组循环引用' not in reasons:
            inspected[target] = tuple(dict.fromkeys(reasons))
        return reasons

    seen = {}
    for module_id in plan.module_ids:
        module = modules.get(module_id)
        if not module:
            errors.append(f"模块 {module_id} 不存在")
            continue
        if module.target not in valid:
            errors.append(f"模块「{module.name}」的出口「{module.target}」不存在")
        if module.strict:
            for reason in dict.fromkeys(inspect(module.target)):
                errors.append(f"严格模块「{module.name}」：{reason}")
        for match in module.matches:
            if match.kind.startswith("IP-CIDR"):
                try:
                    network = ipaddress.ip_network(match.value, strict=False)
                    if (match.kind == "IP-CIDR6") != (network.version == 6):
                        raise ValueError()
                except ValueError:
                    errors.append(f"模块「{module.name}」有无效网段：{match.value}")
            key = (match.kind, match.value.casefold())
            if key in seen:
                warnings.append(f"「{module.name}」与「{seen[key]}」匹配条件重复，先匹配的模块优先")
            seen.setdefault(key, module.name)
            rule = f"{match.kind},{match.value},{module.target}"
            if match.kind.startswith("IP-CIDR"):
                rule += ",no-resolve"
            rules.append(rule)
            origins.append({"module": module.name, "rule": rule, "strict": module.strict})
    upstream = list(config.get("rules", []))
    if plan.default_target:
        if plan.default_target not in valid:
            errors.append("默认出口不存在")
        upstream = [r for r in upstream if not r.upper().startswith(("MATCH,", "FINAL,"))]
        upstream.append(f"MATCH,{plan.default_target}")
    config["rules"] = rules + upstream
    return {"config": config, "yaml": dump_config(config), "errors": errors, "warnings": warnings,
            "module_rules": origins, "workspace_revision": workspace.revision}
