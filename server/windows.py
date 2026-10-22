"""Read-only privilege and process inventory for TUN conflict checks."""
import ctypes
from ctypes import wintypes
import os


def is_admin():
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def other_cores(own_pid=None):
    if os.name != "nt":
        return []

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                    ("exe", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        return ["无法完成内核进程检查"]
    entry = ProcessEntry()
    entry.size = ctypes.sizeof(entry)
    result = []
    try:
        found = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while found:
            name = entry.exe.lower()
            if entry.pid != own_pid and name.endswith(".exe") and any(term in name for term in ("mihomo", "clash-meta", "clash-core")):
                result.append(f"{entry.exe} (PID {entry.pid})")
            found = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result
