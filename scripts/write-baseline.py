from __future__ import annotations
import hashlib
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029'
MANIFEST = ROOT / 'artifacts' / 'memory' / 'checkpoint-20261029' / 'SHA256SUMS.txt'
ns = runpy.run_path(str(ROOT / 'scripts' / 'rebuild-memory-baseline.py'))
runtime_baseline, api_baseline = ns['runtime_baseline'], ns['api_baseline']

ORIGINAL_CACHE = '''"""Small immutable-by-copy single-flight caches, bounded by revision and capacity."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock


class RevisionCache:
    def __init__(self, capacity=16):
        self.capacity = capacity
        self.lock = Lock()
        self.values = OrderedDict()
        self.pending = {}
        self.hits = self.misses = 0

    def get(self, key, build):
        with self.lock:
            if key in self.values:
                self.hits += 1
                self.values.move_to_end(key)
                return deepcopy(self.values[key])
            future = self.pending.get(key)
            owner = future is None
            if owner:
                self.misses += 1
                future = self.pending[key] = Future()
        if not owner:
            return deepcopy(future.result())
        try:
            value = build()
            with self.lock:
                self.values[key] = deepcopy(value)
                while len(self.values) > self.capacity:
                    self.values.popitem(last=False)
            future.set_result(value)
            return deepcopy(value)
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def stats(self):
        with self.lock:
            return dict(entries=len(self.values), in_flight=len(self.pending), hits=self.hits, misses=self.misses)
'''

# The checkpoint captured a mixed final newline (LF body, CRLF last line).
ORIGINAL_CACHE = ORIGINAL_CACHE[:-1] + '\r\n'

ORIGINAL_RESOURCES = '''"""Read-only memory sampling for this application's process tree and managed core."""
from __future__ import annotations

import os
from pathlib import Path
import threading
import time


DESKTOP_NAMES = {'clashstudio.exe', 'clash-studio.exe', 'clash-studio', 'clash studio'}


def application_pids(rows, service_pid, parent_pid, core_pid=0):
    parent = rows.get(parent_pid, {})
    root = parent_pid if (parent.get('name', '').lower() in DESKTOP_NAMES
                          and rows.get(service_pid, {}).get('parent') == parent_pid) else service_pid
    children = {}
    for pid, row in rows.items():
        children.setdefault(row['parent'], []).append(pid)
    found, todo = set(), [root]
    while todo:
        pid = todo.pop()
        if pid in found or pid not in rows:
            continue
        found.add(pid)
        todo.extend(children.get(pid, []))
    if core_pid and rows.get(core_pid, {}).get('name', '').lower().startswith('mihomo'):
        found.add(core_pid)
    return found


def windows_inventory():
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD),
                    ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG), ('flags', wintypes.DWORD),
                    ('name', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError('Process inventory unavailable')
    try:
        entry = Entry(); entry.size = ctypes.sizeof(entry)
        ok, rows = kernel.Process32FirstW(handle, ctypes.byref(entry)), {}
        while ok and len(rows) < 32768:
            rows[entry.pid] = {'parent': entry.parent, 'name': entry.name}
            ok = kernel.Process32NextW(handle, ctypes.byref(entry))
        return rows
    finally:
        kernel.CloseHandle(handle)


def windows_working_set(pid):
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in ('peak', 'working_set', 'pool_peak', 'pool', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return None
    try:
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        return int(counters.working_set) if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb) else None
    finally:
        kernel.CloseHandle(handle)


def inventory():
    if os.name == 'nt':
        return windows_inventory()
    rows = {}
    if Path('/proc').is_dir():
        for item in Path('/proc').iterdir():
            if not item.name.isdigit():
                continue
            try:
                stat = (item / 'stat').read_text()
                end = stat.rfind(')')
                rows[int(item.name)] = {'name': stat[stat.index('(') + 1:end], 'parent': int(stat[end + 2:].split()[1])}
            except (OSError, ValueError, IndexError):
                continue
    return rows


def resident_bytes(pid):
    if os.name == 'nt':
        return windows_working_set(pid)
    try:
        return int(Path(f'/proc/{pid}/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    except (OSError, ValueError, IndexError):
        return None


class ResourceMonitor:
    def __init__(self, runtime):
        self.runtime, self.lock, self.cached = runtime, threading.Lock(), None
        self.cached_at = 0.0

    def memory(self):
        with self.lock:
            if self.cached is not None and time.monotonic() - self.cached_at < 1:
                return self.cached
            groups = {kind: {'kind': kind, 'bytes': 0, 'process_count': 0, 'unreadable_count': 0}
                      for kind in ('interface', 'service', 'core')}
            readable = missing = 0
            try:
                rows = inventory()
                with self.runtime.lock:
                    core_pid = getattr(self.runtime.process, 'pid', 0) if self.runtime.active else 0
                for pid in application_pids(rows, os.getpid(), os.getppid(), core_pid):
                    name = rows[pid]['name'].lower()
                    kind = 'core' if name.startswith('mihomo') else 'service' if name.startswith('python') else 'interface'
                    group = groups[kind]; group['process_count'] += 1
                    value = resident_bytes(pid)
                    if value is None:
                        missing += 1; group['unreadable_count'] += 1
                    else:
                        readable += 1; group['bytes'] += value
            except OSError:
                missing += 1
            for group in groups.values():
                if group['unreadable_count'] == group['process_count'] and group['process_count']:
                    group['bytes'] = None
            value = {'status': 'unavailable' if not readable else 'partial' if missing else 'ok',
                     'total_bytes': sum(g['bytes'] or 0 for g in groups.values()) if readable else None,
                     'processes': list(groups.values()), 'unreadable_count': missing,
                     'sampled_at': time.time(), 'method': 'working_set_sum', 'scope': 'application_process_tree'}
            self.cached, self.cached_at = value, time.monotonic()
            return value
'''

ORIGINAL_TEST_RESOURCES = '''import os
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient

from server.api import build_app
from server.resources import ResourceMonitor, application_pids, resident_bytes


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
        return {parent: 1024, service: 2048, 999999: None}[pid]
    monkeypatch.setattr('server.resources.resident_bytes', sample)
    monitor = ResourceMonitor(SimpleNamespace(lock=threading.RLock(), process=None, active=None))
    value = monitor.memory()
    assert value['status'] == 'partial' and value['total_bytes'] == 3072
    assert value['unreadable_count'] == 1
    assert value['processes'][2]['bytes'] is None
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
        assert all(set(p) == {'kind', 'bytes', 'process_count', 'unreadable_count'} for p in value['processes'])
'''

files = {
    'server/cache.py': ORIGINAL_CACHE,
    'server/resources.py': ORIGINAL_RESOURCES,
    'tests/test_resources.py': ORIGINAL_TEST_RESOURCES,
    'server/runtime.py': runtime_baseline(),
    'server/api.py': api_baseline(),
}

manifest = {}
for line in MANIFEST.read_text(encoding='utf-8').splitlines():
    if '|' in line:
        rel, digest, size = line.split('|')
        manifest[rel.replace('\\', '/')] = (digest, int(size))

for rel, text in files.items():
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = manifest.get(rel)
    matched = False
    for newline in ('\n', '\r\n'):
        with path.open('w', encoding='utf-8', newline=newline) as handle:
            handle.write(text)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest().upper()
        if expected and digest == expected[0]:
            matched = True
            break
    status = 'MATCH' if matched else 'MISMATCH'
    print(f'{status} {rel} newline={newline!r} bytes={len(data)} sha={digest[:12]} expected={expected[0][:12] if expected else "none"}')
