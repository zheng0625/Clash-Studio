from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029'
MANIFEST = ROOT / 'artifacts' / 'memory' / 'checkpoint-20261029' / 'SHA256SUMS.txt'

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def replace_once(text, new, old, label):
    if text.count(new) != 1:
        raise SystemExit(f'{label}: expected one match for {new[:70]!r}, got {text.count(new)}')
    return text.replace(new, old, 1)

def runtime_baseline():
    text = read('server/runtime.py')
    text = replace_once(text, '''    def invalidate_connections(self):
        # Lifecycle paths hold lifecycle_lock; lifecycle_lock -> sample_lock is
        # the only order used, matching stop/apply/traffic.
        with self.sample_lock:
            self._clear_connection_cache_locked()

    def _clear_connection_cache_locked(self):
        self._connection_sample = None
        self._connection_session = None
        self._connection_at = 0.0
        self._connection_wire = None

    def change_routing_mode(self, mode):''', '    def change_routing_mode(self, mode):', 'runtime methods')
    text = replace_once(text, '''            # The request result is owned by this cache; callers only ever
            # receive copies, so the second full deepcopy is unnecessary.
            self._connection_sample, self._connection_session, self._connection_at = value, process, time.monotonic()
            return self._sample_result(value, summary)''', '''            self._connection_sample, self._connection_session, self._connection_at = copy.deepcopy(value), process, time.monotonic()
            return self._sample_result(value, True) if summary else value''', 'runtime store')
    text = replace_once(text, '''            if not self.alive() or self._connection_sample is None:
                self._clear_connection_cache_locked()
                return json.dumps(summary | {'connections': []}).encode()''', '''            if not self.alive():
                return json.dumps(summary | {'connections': []}).encode()''', 'runtime json')
    text = replace_once(text, '''                self.invalidate_egress()
                self.invalidate_connections()
                self.last_composed = copy.deepcopy(composed)''', '''                self.invalidate_egress()
                self._connection_at = 0
                self.last_composed = copy.deepcopy(composed)''', 'runtime apply')
    text = replace_once(text, '''                self._retire_client()
                self.invalidate_connections()
                self.invalidate_egress()''', '''                self._retire_client()
                self.invalidate_egress()''', 'runtime monitor')
    text = replace_once(text, '''            self.process = None
            self.invalidate_connections()
            self.invalidate_egress()''', '''            self.process = None
            self._connection_at = 0
            self.invalidate_egress()''', 'runtime stop')
    return text

def api_baseline():
    text = read('server/api.py')
    text = replace_once(text, 'from .cache import CacheBusy, RevisionCache', 'from .cache import RevisionCache', 'api import')
    text = replace_once(text, '''    def cached_composition(key, build):
        try:
            return compositions.get(key, build)
        except CacheBusy as error:
            raise HTTPException(503, '配置合成繁忙，请稍后重试') from error

    def profile_config(profile_id):
        profile = row(profile_id)
        state = workspace.load()
        result = cached_composition((profile_id, profile["revision"], state.revision),
                                    lambda: compose(profile["published"], profile_id, state))
        return profile, result''', '''    def profile_config(profile_id):
        profile = row(profile_id)
        state = workspace.load()
        result = compositions.get((profile_id, profile["revision"], state.revision), lambda: compose(profile["published"], profile_id, state))
        return profile, result''', 'api profile')
    text = replace_once(text, '    compositions = RevisionCache()', '    compositions = RevisionCache(16)', 'api cache ctor')
    text = replace_once(text, "        composed = cached_composition((body.profile_id, profile['revision'], state.revision), lambda: compose(profile['published'], body.profile_id, state))",
                        "        composed = compositions.get((body.profile_id, profile['revision'], state.revision), lambda: compose(profile['published'], body.profile_id, state))", 'api apply compose')
    text = replace_once(text, '        runtime.invalidate_connections()', '        runtime._connection_at = 0', 'api close connection')
    return text

def main():
    replacements = {
        'server/runtime.py': runtime_baseline(),
        'server/api.py': api_baseline(),
    }
    print('backend files rebuilt:', sorted(replacements))
    for rel, text in replacements.items():
        print(rel, len(text))

if __name__ == '__main__':
    main()
