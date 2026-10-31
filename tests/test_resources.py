import os
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from server.api import build_app
from server.resources import ResourceMonitor, _query_private_working_set, application_pids, resident_bytes


def test_tree_includes_desktop_children_but_not_other_applications():
    rows = {1: {'name': 'ClashStudio.exe', 'parent': 99},
            2: {'name': 'python.exe', 'parent': 1},
            3: {'name': 'msedgewebview2.exe', 'parent': 1},
            4: {'name': 'mihomo.exe', 'parent': 2},
            5: {'name': 'other.exe', 'parent': 99}}
    assert application_pids(rows, 2, 1) == {1, 2, 3, 4}
    rows[1]['name'] = 'python.exe'
    assert application_pids(rows, 2, 1) == {2, 4}


def test_explicit_managed_core_does_not_admit_an_unrelated_pid():
    rows = {1: {'name': 'python.exe', 'parent': 0},
            2: {'name': 'mihomo-windows-amd64-compatible.exe', 'parent': 999},
            3: {'name': 'other.exe', 'parent': 999}}
    assert application_pids(rows, 1, 0, 2) == {1, 2}
    assert application_pids(rows, 1, 0, 3) == {1}


def test_memory_sum_partial_values_and_cache(monkeypatch):
    service, parent = os.getpid(), os.getppid()
    rows = {parent: {'name': 'ClashStudio.exe', 'parent': 0},
            service: {'name': 'python.exe', 'parent': parent},
            999999: {'name': 'mihomo.exe', 'parent': service}}
    calls = []
    monkeypatch.setattr('server.resources.inventory', lambda: rows)
    def sample(pid):
        calls.append(pid)
        return {parent: {'working_set': 1024, 'private_bytes': 512},
                service: {'working_set': 2048, 'private_bytes': 1024},
                999999: None}[pid]
    monkeypatch.setattr('server.resources.process_memory', sample)
    monitor = ResourceMonitor(SimpleNamespace(lock=threading.RLock(), process=None, active=None))
    value = monitor.memory()
    assert value['status'] == 'partial' and value['total_bytes'] == 3072
    assert value['private_total_bytes'] is None  # one unreadable core process must not be treated as zero
    assert value['unreadable_count'] == 1
    kinds = {part['kind']: part for part in value['processes']}
    assert kinds['probe']['bytes'] is None
    assert kinds['probe']['private_bytes'] is None
    assert monitor.memory() == value and len(calls) == 3


def test_unavailable_memory_is_not_reported_as_zero(monkeypatch):
    monkeypatch.setattr('server.resources.inventory', lambda: {})
    monitor = ResourceMonitor(SimpleNamespace(lock=threading.RLock(), process=None, active=None))
    assert monitor.memory()['status'] == 'unavailable'
    assert monitor.memory()['total_bytes'] is None


def test_real_process_memory_and_api(tmp_path):
    assert resident_bytes(os.getpid()) > 0
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get('/api/client/resources/memory', headers={'X-Clash-Studio': '1'})
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['total_bytes'] > 0
        assert value['method'] == 'working_set_sum'
        assert value['total_bytes'] == sum(p['bytes'] or 0 for p in value['processes'])
        assert value['private_method'] in {'private_commit_sum', 'rss_anon_sum'}
        assert value['private_total_bytes'] == sum(p['private_bytes'] or 0 for p in value['processes'])
        assert all(set(p) == {'kind', 'bytes', 'private_bytes', 'process_count', 'unreadable_count', 'private_unreadable_count',
                             'private_working_set_bytes', 'private_working_set_unreadable_count'}
                   for p in value['processes'])
        if os.name == 'nt':
            assert value['ram_method'] == 'private_working_set_sum'
            assert value['private_working_set_total_bytes'] > 0
            assert value['private_working_set_total_bytes'] <= value['total_bytes']
        else:
            assert value['ram_method'] == 'working_set_sum'


def test_memory_roles_split_host_webview_main_and_probe(monkeypatch):
    service, parent = os.getpid(), os.getppid()
    rows = {parent: {'name': 'clash-studio.exe', 'parent': 0},
            service: {'name': 'python.exe', 'parent': parent},
            10: {'name': 'msedgewebview2.exe', 'parent': service},
            20: {'name': 'mihomo.exe', 'parent': service},
            21: {'name': 'mihomo.exe', 'parent': service}}
    monkeypatch.setattr('server.resources.inventory', lambda: rows)
    monkeypatch.setattr('server.resources.process_memory',
                        lambda pid: {'working_set': 1, 'private_bytes': 1})
    runtime = SimpleNamespace(lock=threading.RLock(), process=SimpleNamespace(pid=20), active=object())
    value = ResourceMonitor(runtime).memory()
    kinds = {part['kind']: part for part in value['processes']}
    assert kinds['desktop']['bytes'] == 1
    assert kinds['webview']['bytes'] == 1
    assert kinds['service']['bytes'] == 1
    assert kinds['core']['bytes'] == 1
    assert kinds['probe']['bytes'] == 1
    assert kinds['other']['process_count'] == 0
    assert value['total_bytes'] == 5


def test_private_working_set_does_not_mix_shared_pages_or_commit(monkeypatch):
    service = os.getpid()
    monkeypatch.setattr('server.resources.inventory', lambda: {
        service: {'name': 'python.exe', 'parent': 0},
        10: {'name': 'msedgewebview2.exe', 'parent': service},
        11: {'name': 'msedgewebview2.exe', 'parent': service}})
    samples = {
        service: {'working_set': 1000, 'private_bytes': 900, 'private_working_set': 300},
        10: {'working_set': 2000, 'private_bytes': 1600, 'private_working_set': 400},
        11: {'working_set': 100, 'private_bytes': 200, 'private_working_set': 0}}
    monkeypatch.setattr('server.resources.process_memory', samples.get)
    runtime = SimpleNamespace(lock=threading.RLock(), process=None, active=None)
    value = ResourceMonitor(runtime).memory()
    assert value['total_bytes'] == 3100
    assert value['private_total_bytes'] == 2700
    assert value['private_working_set_total_bytes'] == 700
    assert value['private_working_set_status'] == 'ok'  # readable zero is valid
    samples[10]['private_working_set'] = None
    value = ResourceMonitor(runtime).memory()
    assert value['private_working_set_total_bytes'] == 300
    assert value['private_working_set_status'] == 'partial'
    webview = next(g for g in value['processes'] if g['kind'] == 'webview')
    assert webview['private_working_set_bytes'] == 0
    assert webview['private_working_set_unreadable_count'] == 1
    for sample in samples.values():
        sample['private_working_set'] = None
    value = ResourceMonitor(runtime).memory()
    assert value['private_working_set_total_bytes'] is None
    assert value['private_working_set_status'] == 'unavailable'
    assert value['total_bytes'] == 3100  # diagnostic fields remain available


def test_legacy_private_working_set_counts_shared_bit_not_share_count():
    calls = []
    def query(handle, buffer, size):
        calls.append(size)
        if len(calls) == 1:
            buffer[0] = 20000  # ERROR_BAD_LENGTH provides required count
            return False
        buffer[0] = 4
        buffer[1] = 4                 # private
        buffer[2] = 4 | (1 << 8) | (1 << 5)  # shareable, currently one user
        buffer[3] = 4 | (1 << 8) | (3 << 5)  # shareable, three users
        buffer[4] = 4                 # private
        return True
    assert _query_private_working_set(query, 1, 4096, lambda: 24) == 8192
    assert len(calls) == 2 and calls[1] > calls[0]


def test_legacy_private_working_set_failure_and_allocation_are_bounded():
    calls = []
    def too_large(handle, buffer, size):
        calls.append(size)
        buffer[0] = 2**30
        return False
    assert _query_private_working_set(too_large, 1, 4096, lambda: 24) is None
    assert len(calls) == 1
    assert _query_private_working_set(lambda *args: False, 1, 4096, lambda: 5) is None


@pytest.mark.skipif(os.name != 'nt', reason='Windows memory counters')
def test_windows_private_working_set_matches_legacy_page_query():
    import ctypes
    import mmap
    from ctypes import wintypes
    from server.resources import windows_memory
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.QueryWorkingSet.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    psapi.QueryWorkingSet.restype = wintypes.BOOL
    expected = _query_private_working_set(psapi.QueryWorkingSet, kernel.GetCurrentProcess(), mmap.PAGESIZE, ctypes.get_last_error)
    value = windows_memory(os.getpid())
    assert expected is not None and value['private_working_set'] is not None
    # The fallback allocates its own buffer, so allow pages touched between reads.
    assert abs(expected - value['private_working_set']) < 8 * 1024 * 1024
