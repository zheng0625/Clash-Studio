"""Reproducible synthetic baseline; no network, proxy or VPN changes."""
import json
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
from app.engine import dump_config
from server.cache import RevisionCache
from server.modules import Workspace, compose
from server.runtime import Runtime


def measure(function, count=3):
    durations = []
    tracemalloc.start()
    for _ in range(count):
        started = time.perf_counter()
        function()
        durations.append((time.perf_counter() - started) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return dict(median_ms=round(statistics.median(durations), 3), peak_bytes=peak, calls=count)


def main():
    result = {'kind':'synthetic-only', 'python':sys.version.split()[0], 'composition':[]}
    for nodes, rules in ((50, 501), (200, 3001)):
        config = dict(proxies=[dict(name=f'node-{i}', type='socks5', server='example.invalid', port=9) for i in range(nodes)],
                      **{'proxy-groups':[dict(name='Work', type='select', proxies=[f'node-{i}' for i in range(nodes)])]},
                      rules=[f'DOMAIN-SUFFIX,example-{i}.invalid,Work' for i in range(rules-1)]+['MATCH,Work'])
        yaml = dump_config(config)
        calls = [0]
        def build():
            calls[0] += 1
            return compose(yaml, 'p', Workspace())
        baseline = measure(build)
        baseline['compose_calls'] = calls[0]
        cache = RevisionCache()
        calls[0] = 0
        cold = measure(lambda:cache.get(('p', 1, 1), build), 1)
        warm = measure(lambda:cache.get(('p', 1, 1), build))
        warm['compose_calls'] = calls[0] - 1
        result['composition'].append(dict(nodes=nodes, rules=rules, yaml_bytes=len(yaml.encode()), baseline=baseline, cold=cold, warm=warm))
    with tempfile.TemporaryDirectory() as directory:
        runtime = Runtime(Path(directory))
        runtime.process = SimpleNamespace(pid=123, poll=lambda:None, terminate=lambda:None, kill=lambda:None, wait=lambda **kwargs:0)
        payload = json.dumps(dict(connections=[dict(id=str(i), metadata=dict(host=f'example-{i}.invalid'), upload=i, download=i*2) for i in range(5000)], uploadTotal=10000, downloadTotal=20000))
        requests = [0]
        def sample(*args, **kwargs):
            requests[0] += 1
            return json.loads(payload)
        runtime.request = sample
        def independent_requests():
            responses = []
            for connection_view in (False, True, False, True):
                value = sample()
                responses.append(json.dumps(value) if connection_view else dict(upload=value['uploadTotal'], download=value['downloadTotal'], connections=len(value['connections'])))
            return responses
        baseline = measure(independent_requests, 1)
        baseline.update(requests=requests[0], bytes=len(payload.encode())*requests[0])
        requests[0] = 0
        optimized = measure(lambda:(runtime.traffic(), runtime.connection_json(), runtime.traffic(), runtime.connection_json()), 1)
        optimized.update(requests=requests[0], bytes=len(payload.encode())*requests[0])
        result['connections'] = dict(entries=5000, baseline=baseline, shared_snapshot=optimized)
        runtime._proxy_cache = dict(supported=False, owned=False)
        runtime._proxy_cache_at = time.monotonic()
        durations = []
        with runtime.lifecycle_lock:
            def statuses():
                for _ in range(200):
                    start=time.perf_counter();runtime.status();durations.append((time.perf_counter()-start)*1000)
            thread=threading.Thread(target=statuses);thread.start();thread.join(5)
            assert not thread.is_alive(), 'status blocked on lifecycle lock'
        durations.sort()
        result['status_during_lifecycle_lock'] = dict(samples=len(durations), p50_ms=round(durations[99],3),p95_ms=round(durations[189],3))
        # Entry+byte budget under distinct revision keys; oversized entries must not be retained.
        budget = RevisionCache(capacity=8, max_bytes=8*1024*1024)
        for index in range(16):
            budget.get(('budget', index), lambda index=index: dict(compose(yaml, 'p', Workspace()), key=index))
        stats = budget.stats()
        result['composition_budget'] = dict(keys=16, entries=stats['entries'], bytes=stats['bytes'],
                                           max_bytes=stats['max_bytes'], evictions=stats['evictions'],
                                           oversized=stats['oversized'], method=stats['method'])
        # Stopping must release cached connection objects/bytes/session while keeping totals.
        runtime._stop_locked(final_sample=False, report=False)
        result['connection_cleanup'] = dict(
            sample_released=runtime._connection_sample is None,
            wire_released=runtime._connection_wire is None,
            session_released=runtime._connection_session is None,
            final_download_retained=runtime.last_traffic['download'] == 20000,
            final_running_flag=runtime.last_traffic['running'])
    target = ROOT/'artifacts'/'backend-benchmark.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
