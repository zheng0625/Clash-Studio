"""Session-scoped, local named-pipe broker for an elevated Mihomo child.

The helper accepts JSON only, a fixed binary, and generated runtime candidates.
It owns a kill-on-close job and exits if its parent or pipe disappears.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from fastapi import HTTPException


def user_sid():
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        data = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, data, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        text = wintypes.LPWSTR()
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    finally:
        kernel.CloseHandle(token)


class Elevation:
    def __init__(self, home):
        self.home = Path(home)
        self.connection = None
        self.lock = threading.RLock()
        self.token = ''

    @property
    def ready(self):
        return self.connection is not None

    def ensure(self):
        with self.lock:
            if self.ready:
                try:
                    self.rpc('ping')
                    return
                except HTTPException:
                    pass
            if os.name != 'nt':
                raise HTTPException(409, '管理员助手仅支持 Windows')
            from multiprocessing.connection import Client
            pipe = r'\\.\pipe\ClashStudio-' + secrets.token_hex(20)
            self.token = secrets.token_hex(32)
            python = Path(sys.executable).with_name('pythonw.exe')
            args = subprocess.list2cmdline(['-I', '-B', str(self.home / 'run.py'), '--core-helper', pipe, self.token, str(os.getpid()), user_sid()])
            shell = ctypes.WinDLL('shell32', use_last_error=True)
            shell.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
            shell.ShellExecuteW.restype = ctypes.c_ssize_t
            result = shell.ShellExecuteW(None, 'runas', str(python), args, str(self.home), 0)
            if result <= 32:
                raise HTTPException(409, '管理员授权已取消或助手未能启动，原模式保持不变')
            until = time.monotonic() + 25
            while time.monotonic() < until:
                try:
                    # Probe existence before Client's potentially long pipe wait.
                    import _winapi
                    _winapi.WaitNamedPipe(pipe, 200)
                    self.connection = Client(pipe, family='AF_PIPE')
                    self.rpc('ping')
                    return
                except (OSError, HTTPException):
                    self.disconnect()
                    time.sleep(.1)
            raise HTTPException(504, '管理员助手连接超时，原模式保持不变')

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.connection = None

    def rpc(self, operation, **values):
        with self.lock:
            if not self.connection:
                raise HTTPException(409, '管理员助手未连接，请重新申请权限')
            try:
                self.connection.send_bytes(json.dumps({'token': self.token, 'op': operation, **values}).encode())
                if not self.connection.poll(12):
                    raise OSError('helper timeout')
                result = json.loads(self.connection.recv_bytes(65536))
                if not result.get('ok'):
                    raise HTTPException(502, result.get('error', '管理员助手操作失败'))
                return result
            except (OSError, EOFError, ValueError):
                self.disconnect()
                raise HTTPException(502, '管理员助手连接已断开；请检查内核状态并重新申请权限') from None

    def launch(self, candidate):
        result = self.rpc('start', candidate=Path(candidate).name)
        return ElevatedProcess(self, result['pid'])

    def close(self):
        with self.lock:
            if self.ready:
                try:
                    self.rpc('exit')
                except HTTPException:
                    pass
            self.disconnect()


class ElevatedProcess:
    def __init__(self, broker, pid):
        self.broker, self.pid = broker, pid

    def poll(self):
        try:
            return self.broker.rpc('poll', pid=self.pid)['code']
        except HTTPException:
            return -1

    def wait(self, timeout=None):
        start = time.monotonic()
        while (value := self.poll()) is None:
            if timeout is not None and time.monotonic() - start >= timeout:
                raise subprocess.TimeoutExpired('elevated core', timeout)
            time.sleep(.2)
        return value

    def terminate(self):
        self.broker.rpc('stop', pid=self.pid)

    kill = terminate


def run_helper(home, args):
    import _winapi
    from multiprocessing.connection import PipeConnection
    from .job import CoreJob
    from .windows import is_admin
    from app.engine import parse_config
    if not is_admin() or len(args) != 4:
        raise SystemExit('Invalid helper invocation')
    pipe, token, parent, sid = args
    if not pipe.startswith(r'\\.\pipe\ClashStudio-') or len(token) != 64 or not sid.startswith('S-1-') or any(c not in 'S-0123456789' for c in sid):
        raise SystemExit('Invalid helper session')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    parent_handle = kernel.OpenProcess(0x00100000, False, int(parent))
    if not parent_handle:
        raise SystemExit('Parent unavailable')
    job = CoreJob()
    process = None
    connection = None
    log = None
    control = {}
    state_lock = threading.RLock()
    closing = threading.Event()
    directory = (Path(home) / 'data/runtime').resolve()
    def cleanup_core():
        with state_lock:
            closing.set()
            if process and process.poll() is None:
                try:
                    if control:
                        import httpx
                        with httpx.Client(trust_env=False, timeout=2) as client:
                            client.patch('http://' + control['address'] + '/configs', headers={'Authorization': 'Bearer ' + control['secret']}, json={'tun': {'enable': False}})
                except Exception:
                    pass
                try:
                    process.terminate()
                    try:
                        process.wait(2)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(2)
                except (OSError, subprocess.SubprocessError):
                    pass
            job.close()
    def start_core(candidate, config):
        nonlocal process, log, control
        with state_lock:
            if closing.is_set():
                raise OSError('helper closing')
            if log:
                log.close()
            log = (directory / 'core.log').open('ab')
            process = subprocess.Popen([str(Path(home) / 'bin/mihomo-windows-amd64-compatible.exe'), '-d', str(directory), '-f', str(candidate)], stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            job.assign(process)
            control = {'address': config['external-controller'], 'secret': config['secret']}
            return process.pid
    def watch_parent():
        kernel.WaitForSingleObject(parent_handle, 0xffffffff)
        cleanup_core()
        os._exit(0)
    threading.Thread(target=watch_parent, daemon=True).start()
    class Attributes(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('descriptor', ctypes.c_void_p), ('inherit', wintypes.BOOL)]
    descriptor = ctypes.c_void_p()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(f'D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;{sid})', 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    attributes = Attributes(ctypes.sizeof(Attributes), descriptor, False)
    kernel.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Attributes)]
    kernel.CreateNamedPipeW.restype = wintypes.HANDLE
    handle = kernel.CreateNamedPipeW(pipe, 3 | 0x40000000 | 0x00080000, 4 | 2 | 8, 1, 65536, 65536, 0, ctypes.byref(attributes))
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree(descriptor)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    connected = threading.Event()
    def startup_timeout():
        if not connected.wait(35):
            job.close()
            os._exit(0)
    threading.Thread(target=startup_timeout, daemon=True).start()
    try:
        ov = _winapi.ConnectNamedPipe(handle, overlapped=True)
        ov.GetOverlappedResult(True)
        connection = PipeConnection(handle)
        connected.set()
        while True:
            if not connection.poll(1):
                continue
            message = json.loads(connection.recv_bytes(65536))
            if not secrets.compare_digest(message.get('token', ''), token):
                break
            op = message.get('op')
            try:
                result = {'ok': True}
                if op == 'start':
                    if process and process.poll() is None:
                        raise ValueError('助手内核仍在运行')
                    name = message.get('candidate', '')
                    if not name.startswith('candidate-') or not name.endswith('.yaml') or Path(name).name != name:
                        raise ValueError('配置文件路径不合法')
                    candidate = (directory / name).resolve()
                    if candidate.parent != directory:
                        raise ValueError('配置文件不在本程序目录')
                    config = parse_config(candidate.read_text(encoding='utf-8'))
                    address = config.get('external-controller', '')
                    secret = config.get('secret', '')
                    match = re.fullmatch(r'127\.0\.0\.1:(\d{1,5})', address) if isinstance(address, str) else None
                    if not match or not 1024 <= int(match[1]) <= 65535 or not isinstance(secret, str) or not 32 <= len(secret) <= 128 or any(ord(c) < 32 for c in secret):
                        raise ValueError('控制接口配置不合法')
                    if not isinstance(config.get('mixed-port'), int) or not 1024 <= config['mixed-port'] <= 65535:
                        raise ValueError('代理端口配置不合法')
                    if any(key in config for key in ('listeners', 'external-controller-unix', 'external-controller-pipe', 'external-controller-tls', 'external-ui', 'external-ui-url', 'external-ui-name', 'port', 'socks-port', 'redir-port', 'tproxy-port', 'iptables')):
                        raise ValueError('不允许额外控制接口')
                    result['pid'] = start_core(candidate, config)
                elif op in ('poll', 'stop'):
                    if not process or process.pid != message.get('pid'):
                        result['code'] = -1
                    elif op == 'poll':
                        result['code'] = process.poll()
                    elif process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(5)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(3)
                elif op not in ('ping', 'exit'):
                    raise ValueError('不支持的助手操作')
                connection.send_bytes(json.dumps(result).encode())
                if op == 'exit':
                    break
            except (OSError, ValueError, subprocess.SubprocessError):
                connection.send_bytes(json.dumps({'ok': False, 'error': '管理员助手未完成操作，请检查 data/runtime/core.log'}).encode())
    except (OSError, EOFError, ValueError):
        pass
    finally:
        cleanup_core()
        if connection:
            connection.close()
        else:
            kernel.CloseHandle(handle)
        kernel.CloseHandle(parent_handle)
        if log:
            log.close()
