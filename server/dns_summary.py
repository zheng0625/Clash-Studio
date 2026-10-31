"""A bounded, credential-free DNS configuration summary, not a leak detector."""
from urllib.parse import urlsplit


def summarize_dns(config):
    dns = config.get('dns') if isinstance(config, dict) else None
    if not isinstance(dns, dict) or not dns.get('enable'):
        return {'status': 'disabled', 'nameservers': []}
    servers = dns.get('nameserver')
    servers = servers if isinstance(servers, list) else []
    result = []
    for value in servers[:32]:
        if not isinstance(value, str):
            continue
        try:
            # Omit URL paths, query parameters, fragments and user info entirely.
            raw = value.split('#', 1)[0].split('?', 1)[0].strip()
            if '://' in raw:
                parsed = urlsplit(raw)
                host = parsed.hostname
                if not host:
                    continue
                host = '[' + host + ']' if ':' in host else host
                display = parsed.scheme + '://' + host + (':' + str(parsed.port) if parsed.port else '')
            else:
                # Bare IPv4/IPv6, system and resolver names; never expose paths.
                display = raw.rsplit('@', 1)[-1].split('/', 1)[0]
            display = display[:256]
            if display and display not in result:
                result.append(display)
        except (ValueError, TypeError):
            continue
    return {'status': 'ok' if result else 'unavailable', 'nameservers': result}
