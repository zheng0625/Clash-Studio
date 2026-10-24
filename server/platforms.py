"""Stable platform boundary; unsupported integrations never mutate the host."""
from pathlib import Path
import os
import platform
import subprocess
import sys
from fastapi import HTTPException
from .proxy import SystemProxy
from .job import CoreJob
from .elevation import Elevation
from .windows import is_admin, other_cores


def platform_info(system=None, machine=None):
    system = system or sys.platform
    name = {'win32': 'windows', 'darwin': 'macos', 'linux': 'linux'}.get(system, 'unknown')
    raw = (machine or platform.machine()).lower()
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(raw, raw)
    windows = name == 'windows'
    return {'os': name, 'arch': arch, 'id': f'{name}-{arch}', 'capabilities': {
        'system_proxy': windows, 'tun': windows or name == 'linux', 'elevation': windows or name == 'linux',
        'autostart': windows or name == 'linux', 'core': name in ('windows', 'linux', 'macos')}}


def core_binary(resources: Path, info=None):
    info = info or platform_info()
    if info['id'] == 'windows-x64':
        name = 'mihomo-windows-amd64-compatible.exe'
    else:
        arch = {'x64': 'amd64', 'arm64': 'arm64'}.get(info['arch'], info['arch'])
        target = 'darwin' if info['os'] == 'macos' else info['os']
        name = f"mihomo-{target}-{arch}" + ('.exe' if target == 'windows' else '')
    return Path(resources) / 'bin' / name


def process_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


class PlatformServices:
    def __init__(self, paths):
        self.paths, self.info = paths, platform_info()
        if self.info['os'] == 'linux':
            from .gnome_proxy import GnomeProxy
            self.info['capabilities']['system_proxy'] = GnomeProxy.available()

    def proxy(self):
        if self.info['os'] == 'linux' and self.info['capabilities']['system_proxy']:
            from .gnome_proxy import GnomeProxy
            return GnomeProxy(self.paths.data)
        return SystemProxy(self.paths.data)

    def elevation(self):
        if self.info['os'] == 'linux':
            from .linux_tun import LinuxElevation
            return LinuxElevation(self.paths.resources, data_dir=self.paths.data)
        return Elevation(self.paths.resources, data_dir=self.paths.data)

    def job(self):
        return CoreJob()

    def require(self, capability):
        if not self.info['capabilities'].get(capability, False):
            raise HTTPException(501, f"Platform integration unavailable: {capability} ({self.info['id']})")
