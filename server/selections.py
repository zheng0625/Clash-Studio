"""Per-subscription manual choices, independent of a running core."""
import json
import os
from pathlib import Path
import threading


class SelectionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def load(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, ValueError):
            return {}

    def get(self, profile_id):
        with self.lock:
            value = self.load().get(profile_id, {})
            return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(value, dict) else {}

    def set(self, profile_id, group, name):
        with self.lock:
            value = self.load()
            value[profile_id] = {**self.get(profile_id), group: name}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            os.replace(temporary, self.path)

    def overlay(self, profile_id, proxies):
        for group, name in self.get(profile_id).items():
            item = proxies.get(group, {})
            if item.get('type') == 'Selector' and name in item.get('all', []):
                item['now'] = name
