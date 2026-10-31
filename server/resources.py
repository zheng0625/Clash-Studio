"""Read-only memory sampling for this application's process tree and managed core."""
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


def _query_private_working_set(query, handle, page_size, last_error):
    """Legacy PSAPI fallback, bounded to 32 MiB and three snapshot attempts."""
    import ctypes
    capacity = 16384
    limit = 32 * 1024 * 1024 // ctypes.sizeof(ctypes.c_size_t) - 1
    for _ in range(3):
        if capacity > limit:
            return None
        buffer = (ctypes.c_size_t * (capacity + 1))()
        if query(handle, buffer, ctypes.sizeof(buffer)):
            count = buffer[0]
            if count > capacity:
                return None
            # PSAPI_WORKING_SET_BLOCK.Shared is bit 8. ShareCount == 1 is
            # NOT private: a shareable DLL page may currently have one user.
            return sum(not (buffer[index] & (1 << 8)) for index in range(1, count + 1)) * page_size
        if last_error() != 24:  # ERROR_BAD_LENGTH
            return None
        capacity = max(capacity * 2, buffer[0] + 1024)
    return None


def windows_memory(pid):
    """Total/private working sets and private commit, without changing residency."""
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in ('peak', 'working_set', 'pool_peak', 'pool', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak', 'private_usage', 'private_working_set')],
                    ('shared_commit', ctypes.c_ulonglong)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        sentinel = ctypes.c_size_t(-1).value
        counters.private_working_set = sentinel
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            # PROCESS_MEMORY_COUNTERS_EX2 requires a recent Windows update.
            # Preserve the original metrics on systems accepting only EX.
            counters = Counters(); counters.cb = Counters.private_working_set.offset
            counters.private_working_set = sentinel
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return None
        private_working = counters.private_working_set
        if private_working == sentinel:
            import mmap
            query_handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
            private_working = None
            if query_handle:
                try:
                    psapi.QueryWorkingSet.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
                    psapi.QueryWorkingSet.restype = wintypes.BOOL
                    private_working = _query_private_working_set(
                        psapi.QueryWorkingSet, query_handle, mmap.PAGESIZE, ctypes.get_last_error)
                finally:
                    kernel.CloseHandle(query_handle)
        return {'working_set': int(counters.working_set), 'private_bytes': int(counters.private_usage),
                'private_working_set': private_working,
                'peak_working_set': int(counters.peak)}
    finally:
        kernel.CloseHandle(handle)


def windows_working_set(pid):
    value = windows_memory(pid)
    return None if value is None else value['working_set']


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


def private_bytes(pid):
    """Private commit / anonymous RSS for one process.

    Windows uses PROCESS_MEMORY_COUNTERS.PagefileUsage. Linux uses RssAnon,
    which excludes file-backed shared pages but is still not VmData.
    """
    if os.name == 'nt':
        value = windows_memory(pid)
        return None if value is None else value['private_bytes']
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('RssAnon:'):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def process_memory(pid):
    """Return a per-process memory record or None when the process is unreadable."""
    if os.name == 'nt':
        value = windows_memory(pid)
        return None if value is None else {'working_set': value['working_set'], 'private_bytes': value['private_bytes'],
                                          'private_working_set': value['private_working_set']}
    working = resident_bytes(pid)
    if working is None:
        return None
    return {'working_set': working, 'private_bytes': private_bytes(pid)}


def memory_method():
    return 'private_commit_sum' if os.name == 'nt' else 'rss_anon_sum'


class ResourceMonitor:
    def __init__(self, runtime):
        self.runtime, self.lock, self.cached = runtime, threading.Lock(), None
        self.cached_at = 0.0

    def memory(self):
        with self.lock:
            if self.cached is not None and time.monotonic() - self.cached_at < 1:
                return self.cached
            groups = {kind: {'kind': kind, 'bytes': 0, 'private_bytes': 0,
                             'private_working_set_bytes': 0,
                             'process_count': 0, 'unreadable_count': 0,
                             'private_unreadable_count': 0, 'private_working_set_unreadable_count': 0}
                      for kind in ('desktop', 'webview', 'service', 'core', 'probe', 'other')}
            readable = missing = 0
            private_missing = 0
            try:
                rows = inventory()
                with self.runtime.lock:
                    core_pid = getattr(self.runtime.process, 'pid', 0) if self.runtime.active else 0
                for pid in application_pids(rows, os.getpid(), os.getppid(), core_pid):
                    name = rows[pid]['name'].lower()
                    if name.startswith('mihomo'):
                        kind = 'core' if core_pid and pid == core_pid else 'probe'
                    elif name.startswith('python'):
                        kind = 'service'
                    elif name in DESKTOP_NAMES or name.startswith(('clash-studio', 'clashstudio')):
                        kind = 'desktop'
                    elif name.startswith(('msedgewebview2', 'webview2')):
                        kind = 'webview'
                    else:
                        kind = 'other'
                    group = groups[kind]; group['process_count'] += 1
                    sample = process_memory(pid)
                    if sample is None:
                        missing += 1; group['unreadable_count'] += 1
                        group['private_working_set_unreadable_count'] += 1
                    else:
                        readable += 1; group['bytes'] += sample['working_set']
                        private_working = sample.get('private_working_set')
                        if private_working is None:
                            group['private_working_set_unreadable_count'] += 1
                        else:
                            group['private_working_set_bytes'] += private_working
                        if sample['private_bytes'] is None:
                            private_missing += 1
                            group['private_unreadable_count'] += 1
                        else:
                            group['private_bytes'] += sample['private_bytes']
            except OSError:
                missing += 1
            for group in groups.values():
                if group['unreadable_count'] == group['process_count'] and group['process_count']:
                    group['bytes'] = None
                if group['process_count'] and (group['private_unreadable_count'] or group['bytes'] is None):
                    group['private_bytes'] = None
                if group['process_count'] and group['private_working_set_unreadable_count'] == group['process_count']:
                    group['private_working_set_bytes'] = None
            private_complete = all(g['private_bytes'] is not None for g in groups.values())
            private_readable = readable - private_missing
            working_missing = sum(g['private_working_set_unreadable_count'] for g in groups.values())
            working_readable = sum(g['process_count'] for g in groups.values()) - working_missing
            working_status = 'unavailable' if not working_readable else 'partial' if working_missing or missing else 'ok'
            value = {'status': 'unavailable' if not readable else 'partial' if missing else 'ok',
                     'total_bytes': sum(g['bytes'] or 0 for g in groups.values()) if readable else None,
                     'private_total_bytes': sum(g['private_bytes'] or 0 for g in groups.values()) if private_readable and private_complete else None,
                     'processes': list(groups.values()), 'unreadable_count': missing,
                     'sampled_at': time.time(), 'method': 'working_set_sum',
                     'private_method': memory_method(), 'private_scope': 'application_process_tree',
                     'private_working_set_total_bytes': sum(g['private_working_set_bytes'] or 0 for g in groups.values()) if working_readable else None,
                     'private_working_set_status': working_status,
                     'private_working_set_unreadable_count': working_missing,
                     'ram_method': 'private_working_set_sum' if os.name == 'nt' else 'working_set_sum',
                     'scope': 'application_process_tree'}
            self.cached, self.cached_at = value, time.monotonic()
            return value
