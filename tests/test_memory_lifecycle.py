import copy
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from server.runtime import Runtime


class Process:
    pid = 43210
    stopped = False

    def poll(self):
        return 0 if self.stopped else None

    def terminate(self):
        self.stopped = True

    kill = terminate

    def wait(self, **kwargs):
        return 0


def proxy_stub():
    proxy = SimpleNamespace(path=Path('unused-proxy-backup'))
    proxy.restore = lambda: {'restored': True}
    proxy.status = lambda: {'owned': False}
    return proxy


def populated(tmp_path, monkeypatch, count=200):
    runtime = Runtime(tmp_path)
    runtime.process = Process()
    runtime.proxy = proxy_stub()
    payload = {'connections': [{'id': str(i), 'metadata': {'host': f'host-{i}.invalid'}} for i in range(count)],
               'uploadTotal': 1024, 'downloadTotal': 2048}

    def request(method, path, **kwargs):
        if path == '/connections':
            return copy.deepcopy(payload)
        return {}

    monkeypatch.setattr(runtime, 'request', request)
    runtime.connection_snapshot(force=True)
    return runtime, payload


def test_stop_releases_connection_objects_bytes_and_session(tmp_path, monkeypatch):
    runtime, _ = populated(tmp_path, monkeypatch)
    wire = runtime.connection_json()
    assert wire and runtime._connection_sample is not None
    assert runtime._connection_wire is not None
    runtime._stop_locked(final_sample=False, report=False)
    assert runtime._connection_sample is None
    assert runtime._connection_session is None
    assert runtime._connection_wire is None
    assert runtime._connection_at == 0
    assert runtime.last_traffic['running'] is False
    assert runtime.last_traffic['connections'] == 0


def test_monitor_exit_releases_connection_cache(tmp_path, monkeypatch):
    runtime, _ = populated(tmp_path, monkeypatch)
    process = runtime.process
    runtime.monitor(process)
    assert runtime._connection_sample is None
    assert runtime._connection_wire is None


def test_connection_payload_is_not_served_after_process_exit(tmp_path, monkeypatch):
    runtime, _ = populated(tmp_path, monkeypatch)
    runtime.process.stopped = True
    body = runtime.connection_json()
    assert b'host-0.invalid' not in body
    assert runtime._connection_wire is None
    assert runtime._connection_sample is None


def test_invalidate_connections_keeps_final_traffic_totals(tmp_path, monkeypatch):
    runtime, _ = populated(tmp_path, monkeypatch)
    runtime.traffic()
    assert runtime.last_traffic['download'] == 2048
    runtime.invalidate_connections()
    assert runtime._connection_sample is None
    assert runtime.last_traffic['download'] == 2048


def test_stop_waits_for_connection_encoder_and_does_not_repopulate_wire(tmp_path, monkeypatch):
    runtime, _ = populated(tmp_path, monkeypatch)
    runtime._connection_at = 0  # force a fresh /connections request inside the encoder
    original_alive = runtime.alive
    entered, release = threading.Event(), threading.Event()
    calls = {'count': 0}

    def gated_alive():
        value = original_alive()
        calls['count'] += 1
        if calls['count'] == 3:
            entered.set()
            assert release.wait(2)
        return value

    monkeypatch.setattr(runtime, 'alive', gated_alive)
    body = {}

    def encode():
        body['value'] = runtime.connection_json()

    worker = threading.Thread(target=encode)
    worker.start()
    assert entered.wait(1)
    stopper = threading.Thread(target=lambda: runtime._stop_locked(final_sample=False, report=False))
    stopper.start()
    time.sleep(0.1)
    assert stopper.is_alive(), 'stop must wait for the in-flight encoder'
    release.set()
    worker.join(2)
    stopper.join(2)
    assert not worker.is_alive() and not stopper.is_alive()
    value = json.loads(body['value'])
    assert isinstance(value, dict) and value['connections']
    assert runtime._connection_wire is None
    assert runtime._connection_sample is None
    assert runtime._connection_session is None
