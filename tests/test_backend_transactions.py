import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.atomic import atomic_text
from server.cache import RevisionCache
from server.network import NetworkMonitor
from server.operations import Operations
from server.runtime import Runtime


class Process:
    pid = 12345
    stopped = False
    def poll(self):
        return 0 if self.stopped else None
    def terminate(self):
        self.stopped = True
    kill = terminate
    def wait(self, **kwargs):
        return 0


@pytest.fixture
def live(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    runtime.binary.parent.mkdir(parents=True, exist_ok=True)
    runtime.binary.touch()
    runtime.process = Process()
    runtime.active = dict(profile_id='p', title='old', revision=1, workspace_revision=1,
                          mixed_port=17890, hash='old', tun=False)
    runtime.active_row = dict(id='p', title='old', revision=1, enabled=True)
    runtime.last_composed = dict(config={}, errors=[], workspace_revision=1)
    runtime.directory.joinpath('active.yaml').write_text('old', encoding='utf-8')
    proxy = SimpleNamespace(path=tmp_path/'proxy-backup', owned=True, restores=0)
    proxy.status = lambda: dict(owned=proxy.owned)
    def restore():
        proxy.owned = False
        proxy.restores += 1
        return dict(restored=True)
    proxy.restore = restore
    proxy.enable = lambda port: setattr(proxy, 'owned', True)
    runtime.proxy = proxy
    state = dict(loaded='old', calls=[])
    def request(method, path, **kwargs):
        state['calls'].append((method, path))
        if path == '/proxies':
            return {'proxies': {'Work': {'type': 'Selector', 'all': ['A'], 'now': 'A'}}}
        if method == 'PUT' and path.startswith('/configs'):
            state['loaded'] = Path(kwargs['json']['path']).read_text(encoding='utf-8')
        if path == '/configs':
            return {'mixed-port': 17890}
        return {}
    monkeypatch.setattr(runtime, 'request', request)
    monkeypatch.setattr(runtime, 'prepare', lambda *args: 'new')
    monkeypatch.setattr(runtime, 'validate_candidate', lambda *args: None)
    monkeypatch.setattr(runtime, 'verify_tun', lambda enabled: None)
    monkeypatch.setattr(runtime, 'restore_selectors', lambda choices: None)
    return runtime, state


@pytest.mark.parametrize('failure', ['selector', 'write', 'replace', 'capture', 'revision'])
def test_post_load_failures_restore_actual_config_metadata_and_proxy(live, monkeypatch, failure):
    runtime, state = live
    before = copy.deepcopy(runtime.active)
    if failure == 'selector':
        def selectors(choices):
            if state['loaded'] == 'new':
                raise OSError('selector injection')
        monkeypatch.setattr(runtime, 'restore_selectors', selectors)
    elif failure in ('write', 'replace'):
        import server.runtime as module
        real = module.atomic_text
        def persist(path, value):
            if path.name == 'active.yaml' and value == 'new':
                raise OSError(failure)
            return real(path, value)
        monkeypatch.setattr(module, 'atomic_text', persist)
    elif failure == 'capture':
        monkeypatch.setattr(runtime.proxy, 'restore', lambda: (_ for _ in ()).throw(OSError('capture')))
        # The rollback restores ownership through enable, independently of restore.
    checks = []
    def validator():
        checks.append(1)
        if failure == 'revision' and len(checks) == 2:
            raise HTTPException(409, 'revision changed')
    with pytest.raises(HTTPException) as error:
        runtime.apply(dict(config={}, errors=[], workspace_revision=2),
                      dict(id='p', title='new', revision=2, enabled=True), 17890,
                      validator=validator, capture_mode='manual' if failure == 'capture' else None)
    assert error.value.detail['rollback'] == 'verified'
    assert state['loaded'] == 'old'
    assert runtime.active == before
    assert runtime.directory.joinpath('active.yaml').read_text() == 'old'
    assert runtime.alive() and runtime.proxy.owned
    assert not list(runtime.directory.glob('rollback-*.yaml'))


def test_unconfirmed_rollback_stops_even_if_proxy_restore_throws(live, monkeypatch):
    runtime, state = live
    monkeypatch.setattr(runtime, 'restore_selectors', lambda choices: (_ for _ in ()).throw(OSError('always fail')))
    monkeypatch.setattr(runtime.proxy, 'restore', lambda: (_ for _ in ()).throw(OSError('restore failed')))
    with pytest.raises(HTTPException) as error:
        runtime.apply(dict(config={}, errors=[], workspace_revision=2), runtime.active_row, 17890)
    assert error.value.detail['rollback'] == 'stopped'
    assert not runtime.alive() and runtime.active is None


def test_atomic_replace_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path/'state'
    path.write_text('before')
    monkeypatch.setattr('server.atomic.os.replace', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        atomic_text(path, 'after')
    assert path.read_text() == 'before'
    assert list(tmp_path.iterdir()) == [path]


def test_singleflight_revision_eviction_and_mutation_isolation():
    cache = RevisionCache(2)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def build():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return {'nodes': [1]}
    with ThreadPoolExecutor(8) as pool:
        first = pool.submit(cache.get, ('p', 1, 1), build)
        assert entered.wait(1)
        rest = [pool.submit(cache.get, ('p', 1, 1), build) for _ in range(7)]
        release.set()
        first.result()['nodes'].append(2)
        assert all(f.result() == {'nodes': [1]} for f in rest)
    assert len(calls) == 1
    cache.get(('p', 2, 1), lambda: {})
    cache.get(('p', 2, 2), lambda: {})
    assert cache.stats()['entries'] == 2
    assert cache.get(('p', 1, 1), lambda: {'new': True}) == {'new': True}


def test_status_does_not_wait_for_lifecycle_and_sampling_is_shared(live):
    runtime, state = live
    release, entered = threading.Event(), threading.Event()
    def hold():
        with runtime.lifecycle_lock:
            entered.set()
            release.wait(2)
    thread = threading.Thread(target=hold)
    thread.start()
    assert entered.wait(1)
    try:
        started = time.monotonic()
        assert runtime.status()['running']
        runtime.request_cancel()
        assert time.monotonic() - started < .2
    finally:
        release.set()
        thread.join()
    a = runtime.connection_snapshot()
    runtime.traffic()
    b = runtime.connection_snapshot()
    assert a['sampled_at'] == b['sampled_at']
    assert state['calls'].count(('GET', '/connections')) == 1
    runtime.process = Process()
    runtime.connection_snapshot()
    assert state['calls'].count(('GET', '/connections')) == 2


def test_bounded_jobs_cancel_queued_work():
    operations = Operations(2)
    release, entered = threading.Event(), threading.Event()
    calls = []
    def hold():
        entered.set()
        release.wait(2)
        return 'done'
    try:
        first = operations.submit('apply', hold)
        assert entered.wait(1)
        second = operations.submit('apply', lambda: calls.append('obsolete'))
        with pytest.raises(HTTPException) as error:
            operations.submit('apply', lambda: None)
        assert error.value.status_code == 429
        operations.cancel(second['operation_id'])
        release.set()
        operations.executor.shutdown(wait=True)
        assert not calls
        assert operations.get(first['operation_id'])['phase'] == 'succeeded'
        assert operations.get(second['operation_id'])['phase'] == 'cancelled'
    finally:
        release.set()
        operations.close()


def test_explicit_ip_refresh_and_egress_change(live, monkeypatch):
    runtime, _ = live
    monitor = NetworkMonitor(runtime)
    calls = []
    def external(*args):
        calls.append(1)
        return dict(status='ok', ip='192.0.2.1', egress_version=runtime.egress_version)
    monkeypatch.setattr(monitor, '_lookup', external)
    monitor.lookup('proxy')
    assert monitor.lookup('proxy')['cached']
    monitor.lookup('proxy', refresh=True)
    assert len(calls) == 2
    runtime.invalidate_egress()
    monitor.lookup('proxy')
    assert len(calls) == 3


def test_cancel_during_preparation_cannot_be_cleared_at_apply_entry(live):
    runtime, state = live
    epoch = runtime._cancel_epoch
    runtime.request_cancel()
    with pytest.raises(HTTPException) as error:
        runtime.apply(runtime.last_composed, runtime.active_row, 17890, expected_epoch=epoch)
    assert error.value.detail['code'] == 'OPERATION_CANCELLED'
    assert state['loaded'] == 'old'


def test_first_start_failure_releases_launched_process(live, monkeypatch):
    runtime, state = live
    process = Process()
    runtime.process = None
    runtime.active = None
    monkeypatch.setattr('server.runtime.subprocess.Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr(runtime.job, 'assign', lambda process: None)
    monkeypatch.setattr(runtime, 'monitor', lambda process: None)
    monkeypatch.setattr(runtime, 'restore_selectors', lambda choices: (_ for _ in ()).throw(OSError('injected')))
    with pytest.raises(HTTPException) as error:
        runtime.apply(runtime.last_composed, runtime.active_row, 17890)
    assert error.value.detail['rollback'] == 'stopped'
    assert process.stopped and runtime.process is None
    assert not runtime.proxy.owned
    assert runtime.log_handle is None


def test_http_session_pool_reuse_and_inflight_retirement(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    runtime.process = Process()
    clients = []
    entered, release = threading.Event(), threading.Event()
    class Client:
        closed = False
        block = False
        def __init__(self, **kwargs):
            assert kwargs['trust_env'] is False
            clients.append(self)
        def request(self, *args, **kwargs):
            if self.block:
                entered.set()
                assert release.wait(2)
            return SimpleNamespace(content=b'{}', raise_for_status=lambda: None, json=lambda: {})
        def close(self):
            self.closed = True
    monkeypatch.setattr('server.runtime.httpx.Client', Client)
    runtime.request('GET', '/version')
    runtime.request('GET', '/version')
    assert len(clients) == 1
    clients[0].block = True
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(runtime.request, 'GET', '/version')
        assert entered.wait(1)
        runtime._retire_client()
        assert not clients[0].closed
        release.set()
        with pytest.raises(HTTPException) as error:
            pending.result()
        assert error.value.status_code == 409
    assert clients[0].closed
    runtime.process = Process()
    runtime.request('GET', '/version')
    assert len(clients) == 2
    runtime._retire_client()
    assert clients[1].closed


def test_background_api_acceptance_status_and_cancellation(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from server.api import build_app
    app = build_app(tmp_path)
    runtime = app.state.runtime
    entered = threading.Event()
    def slow(*args, **kwargs):
        entered.set()
        while not runtime._cancel.wait(.01):
            pass
        raise HTTPException(409, 'cancelled')
    monkeypatch.setattr(runtime, 'apply', slow)
    headers = {'X-Clash-Studio': '1'}
    with TestClient(app) as client:
        profile = client.post('/api/subscriptions', headers=headers, json={'title':'test', 'source_type':'file', 'yaml':'proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]'}).json()
        revision = client.get('/api/client/workspace').json()['revision']
        response = client.post('/api/client/runtime/apply?background=true', headers=headers, json={'profile_id':profile['id'], 'profile_revision':1, 'workspace_revision':revision, 'proxy_mode':'manual'})
        assert response.status_code == 202
        key = response.json()['operation_id']
        assert entered.wait(1)
        assert client.get('/api/client/runtime').status_code == 200
        stopped = client.post('/api/client/runtime/stop?background=true', headers=headers)
        assert stopped.status_code == 202
        app.state.operations.executor.shutdown(wait=True)
        assert client.get('/api/client/operations/'+key).json()['phase'] == 'cancelled'
        assert client.get('/api/client/diagnostics').json()['operations']['running'] == 0


def test_ip_refreshes_share_only_overlapping_work(live, monkeypatch):
    runtime, _ = live
    monitor = NetworkMonitor(runtime)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def external(*args):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return dict(status='ok', ip='192.0.2.1')
    monkeypatch.setattr(monitor, '_lookup', external)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(monitor.lookup, 'proxy', True)
        assert entered.wait(1)
        second = pool.submit(monitor.lookup, 'proxy', True)
        # Wait until the second caller has joined the same Future.
        time.sleep(.03)
        release.set()
        assert first.result() == second.result()
    assert len(calls) == 1
    monitor.lookup('proxy', True)
    assert len(calls) == 2


def test_ip_result_is_discarded_if_egress_changes_during_lookup(live, monkeypatch):
    runtime, _ = live
    monitor = NetworkMonitor(runtime)
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    def response(*args):
        runtime.invalidate_egress()
        return dict(success=True, ip='192.0.2.1')
    monkeypatch.setattr('server.network.httpx.Client', Client)
    monkeypatch.setattr(monitor, '_json', response)
    with pytest.raises(HTTPException) as error:
        monitor.lookup('proxy', True)
    assert error.value.status_code == 409
    assert not monitor.cache and not monitor.pending
