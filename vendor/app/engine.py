"""Parse source YAML and reapply durable edits without changing the source."""
from __future__ import annotations

import copy
import io
from typing import Any

from ruamel.yaml import YAML
from .ai_rules import managed_match, managed_rules

MAX_BYTES = 8 * 1024 * 1024
BUILTINS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE", "GLOBAL"}
GROUP_TYPES = {"select", "url-test", "fallback", "load-balance", "relay"}


def yaml_codec():
    codec = YAML()
    codec.allow_duplicate_keys = False
    codec.preserve_quotes = True
    codec.width = 120
    return codec


def plain(value: Any, depth=0, budget=None):
    """Reject alias cycles, excessive expansion, and non-JSON YAML values."""
    if budget is None:
        budget = [200_000]
    budget[0] -= 1
    if depth > 60 or budget[0] < 0:
        raise ValueError("配置嵌套过深或 YAML 引用展开过大")
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("配置字段名称必须是字符串")
        return {str(k): plain(v, depth + 1, budget) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v, depth + 1, budget) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError("配置中包含不支持的 YAML 数据类型")


def parse_config(text: str):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("配置文件不能超过 8 MB")
    try:
        # ruamel's round-trip loader can replace recursive aliases with None.
        # Check the syntax tree first so invalid cycles cannot silently change.
        tree = yaml_codec().compose(text)
        from ruamel.yaml.nodes import MappingNode, SequenceNode
        stack, remaining = set(), [200_000]

        def check_tree(node, depth=0):
            remaining[0] -= 1
            if id(node) in stack or depth > 60 or remaining[0] < 0:
                raise ValueError("YAML 包含循环引用、过深嵌套或过大的别名展开")
            stack.add(id(node))
            if isinstance(node, MappingNode):
                for key, value in node.value:
                    check_tree(key, depth + 1)
                    check_tree(value, depth + 1)
            elif isinstance(node, SequenceNode):
                for value in node.value:
                    check_tree(value, depth + 1)
            stack.remove(id(node))

        if tree:
            check_tree(tree)
        config = yaml_codec().load(text)
        if not isinstance(config, dict):
            raise ValueError("需要 Clash/Mihomo YAML 配置；第一版不支持 Base64 节点链接")
        plain(config)
        for field in ("proxies", "proxy-groups", "rules"):
            if field in config and not isinstance(config[field], list):
                raise ValueError(f"{field} 必须是列表")
        for field in ("proxy-providers", "rule-providers", "sub-rules"):
            if field in config and not isinstance(config[field], dict):
                raise ValueError(f"{field} 必须是对象")
        for field in ("proxy-providers", "rule-providers"):
            for provider in config.get(field, {}).values():
                if not isinstance(provider, dict):
                    raise ValueError(f"{field} 中每一项必须是对象")
                if "proxy" in provider and not isinstance(provider["proxy"], str):
                    raise ValueError(f"{field} 中的 proxy 必须是策略名称")
        if not any(k in config for k in ("proxies", "proxy-providers", "proxy-groups")):
            raise ValueError("没有找到节点、代理组或 proxy-providers")
        for field in ("proxies", "proxy-groups"):
            for item in config.get(field, []):
                if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                    raise ValueError(f"{field} 中每一项都需要有效名称")
                if not isinstance(item.get("type"), str):
                    raise ValueError(f"{field} 中每一项都需要 type")
                if "dialer-proxy" in item and not isinstance(item["dialer-proxy"], str):
                    raise ValueError("dialer-proxy 必须是策略名称")
                for key in ("proxies", "use") if field == "proxy-groups" else ():
                    if key in item and (not isinstance(item[key], list) or any(not isinstance(n, str) for n in item[key])):
                        raise ValueError(f"代理组的 {key} 必须是名称字符串列表")
        if any(not isinstance(r, str) for r in config.get("rules", [])):
            raise ValueError("rules 中每一项必须是字符串")
        return config
    except ValueError:
        raise
    except Exception as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f"（第 {mark.line + 1} 行）" if mark else ""
        # Never echo arbitrary YAML fragments, which may contain passwords.
        raise ValueError(f"YAML 解析失败{location}，请检查格式、重复字段或缩进") from None


def dump_config(config):
    stream = io.StringIO()
    yaml_codec().dump(config, stream)
    return stream.getvalue()


def split_rule(rule: str):
    """Split commas outside logical-rule parentheses."""
    depth, start, parts = 0, 0, []
    for i, ch in enumerate(rule):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(rule[start:i].strip())
            start = i + 1
        if depth < 0:
            return []
    if depth:
        return []
    parts.append(rule[start:].strip())
    return parts


def policy_index(parts):
    return len(parts) - (2 if parts and parts[-1].lower() == "no-resolve" else 1)


def rewrite_rule(rule, names):
    parts = split_rule(rule)
    if len(parts) >= 2 and parts[0].upper() != "SUB-RULE":
        index = policy_index(parts)
        parts[index] = names.get(parts[index], parts[index])
        return ",".join(parts)
    return rule


def empty_edits():
    return {"proxy_renames": {}, "excluded_proxies": [], "group_overrides": {},
            "deleted_groups": [], "new_groups": [], "removed_rules": [],
            "added_rules": [], "rule_order": [], "ai_routing": None}


def compile_config(source: str, edits: dict):
    config = copy.deepcopy(parse_config(source))
    errors, warnings = [], []
    edits = {**empty_edits(), **edits}
    renames = dict(edits["proxy_renames"])
    excluded = set(edits["excluded_proxies"])
    source_proxies = {p["name"] for p in config.get("proxies", [])}
    source_groups = {g["name"] for g in config.get("proxy-groups", [])}
    for name in renames.keys() | excluded:
        if name not in source_proxies:
            warnings.append(f"原节点「{name}」已不在订阅中；对应修改暂未应用")
    if "proxies" in config:
        config["proxies"] = [p for p in config["proxies"] if p["name"] not in excluded]
        for proxy in config["proxies"]:
            proxy["name"] = renames.get(proxy["name"], proxy["name"])

    groups = []
    for name in edits["group_overrides"]:
        if name not in source_groups and name not in edits["deleted_groups"]:
            errors.append(f"被修改的代理组「{name}」已从源订阅消失，请清除对应修改或恢复该代理组")
    for group in config.get("proxy-groups", []):
        name = group["name"]
        if name in edits["deleted_groups"]:
            continue
        patch = edits["group_overrides"].get(name, {})
        group.update(copy.deepcopy(patch))
        if group["name"] != name:
            renames[name] = group["name"]
        groups.append(group)
    groups.extend(copy.deepcopy(edits["new_groups"]))
    for group in groups:
        if isinstance(group.get("proxies"), list):
            group["proxies"] = [renames.get(n, n) for n in group["proxies"] if n not in excluded]
    config["proxy-groups"] = groups
    for proxy in config.get("proxies", []):
        if "dialer-proxy" in proxy:
            proxy["dialer-proxy"] = renames.get(proxy["dialer-proxy"], proxy["dialer-proxy"])
    for provider in config.get("proxy-providers", {}).values():
        if isinstance(provider, dict) and "proxy" in provider:
            provider["proxy"] = renames.get(provider["proxy"], provider["proxy"])

    original_rules = config.get("rules", [])
    removed = set(edits["removed_rules"])
    available = [r for r in original_rules if r not in removed] + edits["added_rules"]
    ordered = [r for r in edits["rule_order"] if r in available]
    # Newly arriving upstream rules must stay before the final catch-all.
    rules = list(dict.fromkeys(ordered))
    remaining = [r for r in available if r not in rules]
    if rules:
        final = next((i for i, r in enumerate(rules) if split_rule(r)[0].upper() in ("MATCH", "FINAL")), len(rules))
        rules[final:final] = remaining
    else:
        rules = remaining
    ai_stats = None
    if edits["ai_routing"] and edits["ai_routing"].get("enabled", True):
        ai_group = edits["ai_routing"]["group"]
        retained, overridden = [], 0
        for rule in rules:
            parts = split_rule(rule)
            if len(parts) >= 2 and managed_match(parts[0], parts[1]):
                overridden += 1
            else:
                retained.append(rule)
        rules = managed_rules(ai_group) + retained
        ai_stats = {"rule_count": len(managed_rules(ai_group)), "overridden": overridden,
                    "group": renames.get(ai_group, ai_group)}
        if not any(g["name"] == renames.get(ai_group, ai_group) for g in groups):
            errors.append("AI 分流的代理组已不存在，请重新选择 AI 分流出口或停用预设")
    config["rules"] = [rewrite_rule(r, renames) for r in rules]
    for key, entries in config.get("sub-rules", {}).items():
        if isinstance(entries, list):
            config["sub-rules"][key] = [rewrite_rule(r, renames) if isinstance(r, str) else r for r in entries]

    names = [p.get("name") for p in config.get("proxies", [])] + [g.get("name") for g in groups]
    seen = set()
    for name in names:
        if not isinstance(name, str) or not name.strip() or any(c in name for c in ",\r\n"):
            errors.append("节点和代理组名称不能为空，且不能包含逗号或换行")
        elif name in seen or name in BUILTINS:
            errors.append(f"节点/代理组名称重复或占用内置名称：「{name}」")
        seen.add(name)
    valid = seen | BUILTINS
    providers = config.get("proxy-providers", {})
    rule_providers = config.get("rule-providers", {})
    graph = {}
    for group in groups:
        name = group.get("name", "未命名")
        if group.get("type") not in GROUP_TYPES:
            errors.append(f"代理组「{name}」的类型不受支持")
        members, uses = group.get("proxies", []), group.get("use", [])
        if not isinstance(members, list) or any(not isinstance(n, str) for n in members):
            errors.append(f"代理组「{name}」的 proxies 必须是名称列表")
            continue
        if not isinstance(uses, list) or any(not isinstance(n, str) for n in uses):
            errors.append(f"代理组「{name}」的 use 必须是 provider 名称列表")
            continue
        if not members and not uses and not any(group.get(k) for k in ("include-all", "include-all-proxies", "include-all-providers")):
            errors.append(f"代理组「{name}」没有可用成员")
        for member in members:
            if member not in valid:
                errors.append(f"代理组「{name}」引用了不存在的节点/组「{member}」")
        for use in uses:
            if use not in providers:
                errors.append(f"代理组「{name}」引用了不存在的 provider「{use}」")
        if group.get("type") in ("url-test", "fallback", "load-balance"):
            if not isinstance(group.get("url"), str) or not group["url"].startswith(("https://", "http://")):
                errors.append(f"代理组「{name}」需要有效的 HTTP 测试 URL")
        if "interval" in group and (not isinstance(group["interval"], int) or isinstance(group["interval"], bool) or group["interval"] <= 0):
            errors.append(f"代理组「{name}」的检测间隔必须是正整数")
        graph[name] = members
    visiting, visited = set(), set()
    for start in graph:
        pending = [(start, False)]
        while pending:
            name, exiting = pending.pop()
            if exiting:
                visiting.discard(name)
                visited.add(name)
                continue
            if name in visiting:
                errors.append(f"代理组存在循环引用，涉及「{name}」")
                continue
            if name in visited or name not in graph:
                continue
            visiting.add(name)
            pending.append((name, True))
            pending.extend((member, False) for member in reversed(graph[name]) if member in graph)
    for proxy in config.get("proxies", []):
        if "dialer-proxy" in proxy and proxy["dialer-proxy"] not in valid:
            errors.append(f"节点「{proxy['name']}」的 dialer-proxy 引用不存在")

    def check_rules(entries, prefix="规则"):
        if not isinstance(entries, list):
            errors.append(f"{prefix}必须是列表")
            return
        caught_all = False
        for index, rule in enumerate(entries):
            parts = split_rule(rule) if isinstance(rule, str) else []
            if len(parts) < 2 or any(not p for p in parts):
                errors.append(f"{prefix}第 {index + 1} 条格式无效")
                continue
            kind = parts[0].upper()
            if kind not in ("MATCH", "FINAL") and len(parts) < 3:
                errors.append(f"{prefix}第 {index + 1} 条缺少匹配条件或目标")
                continue
            if caught_all:
                warnings.append(f"{prefix}第 {index + 1} 条位于 MATCH/FINAL 后，可能不会命中")
            if kind in ("MATCH", "FINAL"):
                caught_all = True
            if kind == "SUB-RULE":
                if parts[-1] not in config.get("sub-rules", {}):
                    errors.append(f"{prefix}第 {index + 1} 条引用了不存在的 sub-rule")
                continue
            if parts[policy_index(parts)] not in valid:
                errors.append(f"{prefix}第 {index + 1} 条引用了不存在的目标「{parts[policy_index(parts)]}」")
            if kind == "RULE-SET" and parts[1] not in rule_providers:
                errors.append(f"{prefix}第 {index + 1} 条引用了不存在的 rule-provider「{parts[1]}」")

    check_rules(config["rules"])
    for key, entries in config.get("sub-rules", {}).items():
        check_rules(entries, f"子规则「{key}」")
    if providers:
        warnings.append("外部 proxy-providers 会原样保留；第一版不下载或展开其中的节点")
    return {"yaml": dump_config(config), "config": plain(config),
            "errors": list(dict.fromkeys(errors)), "warnings": list(dict.fromkeys(warnings)),
            "ai_routing": ai_stats}
