"""Build a reversible AI routing draft; never publish or mutate the database."""
import copy

from .ai_rules import AI_GROUP_NAME, catalogue
from .engine import compile_config, empty_edits, parse_config


def create_ai_draft(source: str, edits: dict, outlet: str):
    edits = {**empty_edits(), **copy.deepcopy(edits)}
    config = parse_config(source)
    source_groups = {g["name"]: g for g in config.get("proxy-groups", []) if g["name"] not in edits["deleted_groups"]}
    groups = {key: {**value, **edits["group_overrides"].get(key, {})} for key, value in source_groups.items()}
    groups.update({g["name"]: g for g in edits["new_groups"]})
    nodes = {p["name"] for p in config.get("proxies", []) if p["name"] not in edits["excluded_proxies"]}
    if outlet not in nodes | groups.keys():
        raise ValueError("请选择当前存在且未排除的代理节点或代理组作为 AI 出口")
    previous = edits["ai_routing"] or {}
    target = previous.get("group") if previous.get("group") in groups else None
    if not target:
        target = next((key for key, g in groups.items() if g["name"] == AI_GROUP_NAME), None)
    if not target:
        if AI_GROUP_NAME in nodes:
            raise ValueError("已有节点占用 AI 代理组名称，请先重命名该节点")
        target = AI_GROUP_NAME
        edits["new_groups"].append({"name": target, "type": "select", "proxies": [outlet], "use": [],
                                    "include-all": False, "include-all-proxies": False,
                                    "include-all-providers": False, "filter": "", "exclude-filter": ""})
    elif target == outlet:
        raise ValueError("AI 代理组不能选择自己作为出口")
    else:
        # Clear automatic inclusion for a reused group, so the chosen outlet is
        # exactly what the dialog promises. Other unedited source data is kept.
        patch = {"type": "select", "proxies": [outlet], "use": [], "include-all": False,
                 "include-all-proxies": False, "include-all-providers": False,
                 "filter": "", "exclude-filter": ""}
        if target in source_groups:
            edits["group_overrides"].setdefault(target, {}).update(patch)
        else:
            next(g for g in edits["new_groups"] if g["name"] == target).update(patch)
    edits["ai_routing"] = {"group": target, "enabled": True}
    result = compile_config(source, edits)
    return {"edits": edits, "preview": result, "catalogue_version": catalogue()["version"]}
