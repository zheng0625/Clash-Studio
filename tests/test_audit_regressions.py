"""Fault and interleaving regressions found during the 1.2 audit."""
import hashlib
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.api import build_app
from server.geo_update import FILES, GeoUpdater
from server.probe import ProbeManager
from server.settings import ClientSettings
from server.logs import FailureLog, ProcessLog
from server.operations import Operations


@pytest.fixture
def updater(tmp_path):
    runtime = SimpleNamespace(paths=SimpleNamespace(data=tmp_path / 'data'),
                              home=tmp_path, directory=tmp_path / 'runtime',
                              lock=threading.RLock(), alive=lambda: False)
    return GeoUpdater(runtime)


def test_geodata_directory_failure_clears_busy_and_allows_retry(updater, monkeypatch):
    original = Path.mkdir
    def fail_stage(path, *args, **kwargs):
        if path.parent.name == 'geodata-updates':
            raise OSError('disk full')
        return original(path, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, 'mkdir', fail_stage)
        updater.start()
        updater.thread.join(2)
        assert not updater.thread.is_alive()
        assert not updater.busy() and updater.state['phase'] == 'error'
    monkeypatch.setattr(updater, 'run', lambda: updater.update_state(busy=False, phase='done'))
    updater.start()
    updater.thread.join(2)
    assert updater.state['phase'] == 'done'


def test_geodata_thread_start_failure_releases_busy(updater, monkeypatch):
    monkeypatch.setattr(threading.Thread, 'start', lambda self: (_ for _ in ()).throw(RuntimeError('no threads')))
    with pytest.raises(HTTPException) as error:
        updater.start()
    assert error.value.status_code == 503
    assert not updater.busy() and updater.thread is None


@pytest.mark.parametrize('failure', ['none', 'replace', 'rollback'])
def test_geodata_cleans_staging_but_preserves_failed_rollback(updater, monkeypatch, failure):
    data = b'x' * 2048 + b'\xab\xcd\xefMaxMind.com'
    digest = hashlib.sha256(data).hexdigest()
    def download(client, url, path, limit):
        path.write_bytes((digest + ' file').encode() if url.endswith('.sha256sum') else data)
        return digest, len(data)
    monkeypatch.setattr(updater, 'download', download)
    directories = [updater.runtime.home / 'bin' / 'geodata', updater.runtime.directory]
    for directory in directories:
        directory.mkdir(parents=True)
        for name in FILES:
            (directory / name).write_bytes(b'old')
    if failure != 'none':
        import server.geo_update as module
        replace, copy = module.os.replace, module.shutil.copy2
        def fail_replace(source, destination):
            if destination == updater.runtime.directory / 'geosite.dat':
                raise OSError('replace failed')
            return replace(source, destination)
        def fail_rollback(source, destination):
            if failure == 'rollback' and Path(source).name.startswith('backup-'):
                raise OSError('rollback failed')
            return copy(source, destination)
        monkeypatch.setattr(module.os, 'replace', fail_replace)
        monkeypatch.setattr(module.shutil, 'copy2', fail_rollback)
    updater.start()
    updater.thread.join(5)
    assert not updater.thread.is_alive() and not updater.busy()
    stages = list((updater.runtime.paths.data / 'geodata-updates').iterdir())
    assert bool(stages) == (failure == 'rollback')
    if failure != 'rollback':
        for directory in directories:
            for name in FILES:
                assert (directory / name).read_bytes() == (data if failure == 'none' else b'old')
    assert not list(updater.runtime.home.rglob('*.update'))


@pytest.fixture
def probe(tmp_path, monkeypatch):
    starts = []
    class Core:
        def __init__(self, *args, **kwargs):
            self.directory, self.running = tmp_path, False
            self.settings = SimpleNamespace(save=lambda value: None)
            self.job = SimpleNamespace(close=lambda: None)
        def alive(self):
            return self.running
        def apply(self, *args):
            self.running = True
            starts.append(self)
        def stop(self, **kwargs):
            self.running = False
    class Delay:
        def __init__(self, core):
            pass
        def probe(self, *args):
            return {'status': 'ok'}
    main = SimpleNamespace(home=tmp_path, resource_home=tmp_path, paths=SimpleNamespace(data=tmp_path),
                           binary=tmp_path / 'fake', settings=SimpleNamespace(load=ClientSettings))
    monkeypatch.setattr('server.probe.Runtime', Core)
    monkeypatch.setattr('server.probe.DelayMonitor', Delay)
    manager = ProbeManager(main)
    yield manager, starts
    manager.stop()


def test_stopped_probe_rejects_old_waiter_but_accepts_new_request(probe):
    manager, starts = probe
    entered = threading.Event()
    ticket = manager.ticket()
    def request():
        entered.set()
        return manager.measure({'proxies': []}, 'node', 'gstatic', 1000, ticket)
    with ThreadPoolExecutor(1) as pool:
        with manager.lock:
            pending = pool.submit(request)
            assert entered.wait(1)
            manager.stop()
        with pytest.raises(HTTPException) as error:
            pending.result(timeout=2)
        assert error.value.detail['code'] == 'OPERATION_CANCELLED'
    assert not starts and manager.core is None
    assert manager.measure({'proxies': []}, 'node', 'gstatic', 1000)['status'] == 'ok'
    assert len(starts) == 1


def test_stop_during_probe_start_cleans_new_core(probe, monkeypatch):
    manager, starts = probe
    core_type = __import__('server.probe', fromlist=['Runtime']).Runtime
    apply = core_type.apply
    def cancel_during_start(core, *args):
        apply(core, *args)
        manager.cancel_pending()
    monkeypatch.setattr(core_type, 'apply', cancel_during_start)
    with pytest.raises(HTTPException):
        manager.ensure({'proxies': []})
    assert len(starts) == 1 and not starts[0].alive()
    assert manager.core is None and manager.timer is None


def test_api_stop_invalidates_delay_admitted_before_worker_runs(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = ProbeManager.measure
    def delayed(manager, *args):
        entered.set()
        assert release.wait(3)
        return original(manager, *args)
    monkeypatch.setattr(ProbeManager, 'measure', delayed)
    app = build_app(tmp_path)
    headers = {'X-Clash-Studio': '1'}
    with TestClient(app) as client, ThreadPoolExecutor(1) as pool:
        imported = client.post('/api/subscriptions', headers=headers, json={
            'title': 'queued', 'source_type': 'file',
            'yaml': 'proxies: []\nproxy-groups: []\nrules: ["MATCH,REJECT"]'})
        assert imported.status_code == 201, imported.text
        profile = imported.json()
        body = dict(profile_id=profile['id'], profile_revision=profile['revision'],
                    workspace_revision=1, name='node')
        future = pool.submit(client.post, '/api/client/runtime/delay', headers=headers, json=body)
        try:
            assert entered.wait(2)
            assert client.post('/api/client/runtime/stop', headers=headers).status_code == 200
        finally:
            release.set()
        response = future.result(timeout=3)
        assert response.status_code == 409
        assert response.json()['error']['code'] == 'OPERATION_CANCELLED'
        assert not (tmp_path / 'data' / 'probe').exists()


def test_preview_content_and_revision_share_one_subscription_read(tmp_path, monkeypatch):
    app = build_app(tmp_path)
    reads = []
    def row(key):
        revision = len(reads) + 1
        reads.append(revision)
        return {'revision': revision, 'published': f'proxies: []\nproxy-groups: []\nrules: [MATCH,REJECT]\naudit_revision: {revision}\n', 'last_error': ''}
    monkeypatch.setattr(app.state.store, 'get', row)
    with TestClient(app) as client:
        response = client.get('/api/client/preview/p')
        assert response.status_code == 200
        result = response.json()
        assert result['profile_revision'] == result['config']['audit_revision']
        assert reads == [1]


def test_process_log_drains_large_output_and_bounds_each_file(tmp_path):
    path = tmp_path / 'core.log'
    path.write_bytes(b'old' * 2000)
    log = ProcessLog(path, max_bytes=1024, backups=2)
    process = subprocess.Popen([sys.executable, '-c', "import sys; sys.stdout.buffer.write(b'x'*200000+b'last-entry')"], stdout=subprocess.PIPE)
    log.attach(process.stdout)
    assert process.wait(timeout=5) == 0
    log.close()
    assert not log.thread.is_alive()
    files = list(tmp_path.iterdir())
    assert len(files) == 3
    assert all(file.stat().st_size <= 1024 for file in files)
    assert path.read_bytes().endswith(b'last-entry')


def test_process_log_keeps_draining_when_disk_write_fails(tmp_path, monkeypatch):
    errors = []
    log = ProcessLog(tmp_path / 'core.log', on_error=lambda: errors.append('failed'))
    monkeypatch.setattr(log, 'write', lambda data: (_ for _ in ()).throw(OSError('disk full')))
    process = subprocess.Popen([sys.executable, '-c', "import sys; sys.stdout.buffer.write(b'x'*200000)"], stdout=subprocess.PIPE)
    log.attach(process.stdout)
    assert process.wait(timeout=5) == 0
    log.close()
    assert log.failed and errors == ['failed'] and not log.thread.is_alive()


def test_background_failure_diagnostics_keep_correlation_without_secrets(tmp_path):
    path = tmp_path / 'backend-errors.log'
    failures = FailureLog(path, max_bytes=4096, backups=2)
    operations = Operations(failures=failures)
    def fail():
        try:
            raise OSError('https://subscription.invalid/?token=private-credential')
        except OSError as error:
            raise RuntimeError('password=private-password') from error
    job = operations.submit('apply', fail)
    operations.executor.shutdown(wait=True)
    assert operations.get(job['operation_id'])['phase'] == 'failed'
    failures.close()
    text = path.read_text(encoding='utf-8')
    assert 'private-credential' not in text and 'private-password' not in text
    record = json.loads(text)
    assert record['operation_id'] == job['operation_id'] and record['kind'] == 'apply'
    assert [error['type'] for error in record['errors']] == ['RuntimeError', 'OSError']
    assert record['errors'][0]['frames'][-1]['function'] == 'fail'


def test_diagnostics_rotate(tmp_path):
    path = tmp_path / 'backend-errors.log'
    failures = FailureLog(path, max_bytes=512, backups=2)
    for index in range(30):
        failures.record(RuntimeError('sensitive'), str(index), 'apply')
    failures.close()
    assert len(list(tmp_path.iterdir())) == 3
    assert all(file.stat().st_size <= 512 for file in tmp_path.iterdir())


def test_unexpected_request_records_correlated_redacted_failure(tmp_path):
    app = build_app(tmp_path)
    @app.get('/api/audit-failure')
    def fail():
        raise OSError('subscription-token-private')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/audit-failure')
        assert response.status_code == 500
        key = response.json()['error']['operation_id']
        text = (tmp_path / 'data' / 'backend-errors.log').read_text(encoding='utf-8')
        assert 'subscription-token-private' not in text
        assert json.loads(text)['operation_id'] == key
