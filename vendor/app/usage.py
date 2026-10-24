"""Parse provider quota metadata without exposing subscription URLs or headers."""
import json
import re


def subscription_usage(raw_headers):
    try:
        headers = json.loads(raw_headers) if isinstance(raw_headers, str) else raw_headers
        raw = next((v for k, v in headers.items() if k.lower() == 'subscription-userinfo'), '')
        if not isinstance(raw, str):
            return None
        values = {}
        for part in raw.split(';'):
            key, separator, value = part.strip().partition('=')
            key = key.lower()
            if separator and key in ('upload', 'download', 'total', 'expire'):
                if key in values or not re.fullmatch(r'[0-9]{1,16}', value.strip()):
                    return None
                values[key] = int(value.strip())
        if not all(key in values for key in ('upload', 'download', 'total')):
            return None
        used = values['upload'] + values['download']
        if max(used, values['total']) > 2**53 - 1:
            return None
        total = values['total'] if values['total'] > 0 else None
        return {'used': used, 'total': total,
                'remaining': max(total - used, 0) if total is not None else None,
                'percent': min(100, used / total * 100) if total is not None else None}
    except (ValueError, TypeError, AttributeError):
        return None
