"""Runtime-only DNS protection; the imported profile is never rewritten."""


def protect_dns(config, dns):
    # Never inherit DIRECT from subscription selectors. Filtering also applies
    # when a provider refreshes; an empty group must reject, not use COMPATIBLE.
    groups = list(config.get("proxy-groups") or [])
    names = {p["name"] for p in groups + list(config.get("proxies") or [])}
    name = "ClashStudio-DNS"
    while name in names:
        name += "-protected"
    groups.append({"name": name, "type": "url-test", "include-all": True,
                   "url": "https://www.gstatic.com/generate_204", "interval": 300, "lazy": True,
                   "exclude-type": "Direct|Compatible|Pass|PassRule|Rematch|Dns",
                   "empty-fallback": "REJECT"})
    config["proxy-groups"] = groups
    for key in ("nameserver-policy", "fallback", "fallback-filter",
                "proxy-server-nameserver-policy", "prefer-h3"):
        dns.pop(key, None)
    dns.update({"enable": True, "respect-rules": True,
                "nameserver": [f"https://1.1.1.1/dns-query#{name}", f"https://8.8.8.8/dns-query#{name}"],
                "default-nameserver": ["223.5.5.5"],
                "proxy-server-nameserver": ["https://223.5.5.5/dns-query#DIRECT"],
                "direct-nameserver": ["https://223.5.5.5/dns-query#DIRECT"],
                "direct-nameserver-follow-policy": False})
