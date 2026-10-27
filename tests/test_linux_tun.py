import os
from pathlib import Path
import struct
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.linux_tun import LinuxElevation
from server.platforms import platform_info
from server.runtime import Runtime


@pytest.fixture
def broker(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'geteuid', lambda: 1000, raising=False)
    monkeypatch.setattr(Path, 'is_char_device', lambda _: True)
    monkeypatch.setattr(Path, 'is_file', lambda _: True)
    return LinuxElevation(tmp_path, tmp_path/'data')


def test_authorization_checks_capability_bits(broker, monkeypatch):
    mask = (1 << 10) | (1 << 12) | (1 << 13)
    monkeypatch.setattr(os, 'getxattr', lambda *a: struct.pack('<IIIII', 0x02000001, mask, 0, 0, 0), raising=False)
    assert broker.ready
    monkeypatch.setattr(os, 'getxattr', lambda *a: struct.pack('<IIIII', 0x02000000, mask, 0, 0, 0))
    assert not broker.ready
    monkeypatch.setattr(os, 'getxattr', lambda *a: struct.pack('<IIIII', 0x02000001, 1 << 12, 0, 0, 0))
    assert not broker.ready


def test_authorization_uses_fixed_argv_and_confirms_result(broker, monkeypatch):
    granted = False
    monkeypatch.setattr(LinuxElevation, 'ready', property(lambda _: granted))
    def run(argv, **kwargs):
        nonlocal granted
        assert argv[0:3] == ['/usr/bin/python3', '-I', '-B']
        assert Path(argv[3]).name == 'linux_auth_agent.py'
        assert argv[4] == str(broker.binary)
        assert kwargs['stderr'] == subprocess.PIPE
        assert 'shell' not in kwargs and kwargs['timeout'] == 90
        granted = True
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, 'run', run)
    broker.ensure()
    assert broker.ready


@pytest.mark.parametrize('code', [0, 126, 127])
def test_cancel_or_ineffective_authorization_is_failure(broker, monkeypatch, code):
    monkeypatch.setattr(LinuxElevation, 'ready', property(lambda _: False))
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=code))
    with pytest.raises(HTTPException) as failure:
        broker.ensure()
    assert failure.value.status_code == 409


def test_missing_tun_device_does_not_request_authorization(broker, monkeypatch):
    monkeypatch.setattr(Path, 'is_char_device', lambda _: False)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('Must not request authorization'))
    with pytest.raises(HTTPException) as failure:
        broker.ensure()
    assert failure.value.status_code == 503


def test_linux_tun_dns_redirect_and_real_interface_required(tmp_path, monkeypatch):
    from app.engine import parse_config
    runtime = Runtime(tmp_path)
    runtime.platform.info = platform_info('linux', 'x86_64')
    config = parse_config(runtime.prepare({'config': {'proxies': []}}, 17890, True))
    assert config['tun']['auto-redirect'] and config['tun']['dns-hijack']
    assert config['dns']['fake-ip-range'] == '198.19.0.1/16'
    assert config['dns']['proxy-server-nameserver'] == ['https://dns.alidns.com/dns-query', 'https://doh.pub/dns-query']
    assert config['profile']['store-selected'] and config['profile']['store-fake-ip']
    assert config['sniffer']['sniff']['TLS']['override-destination']
    monkeypatch.setattr(runtime, 'request', lambda *a: {'tun': {'enable': True}})
    def missing(*args):
        raise OSError('No such interface')
    monkeypatch.setattr('socket.if_nametoindex', missing)
    with pytest.raises(HTTPException) as failure:
        runtime.verify_tun(True)
    assert failure.value.status_code == 502


def test_linux_conflicts_exclude_managed_child_and_zombie(tmp_path):
    from server.windows import linux_other_cores
    for pid, name, state, parent in [(101, 'mihomo-linux-amd', 'S', 50), (102, 'mihomo', 'Z', 1),
                                     (103, 'clash-meta', 'S', 1), (104, 'clash-studio', 'S', 1)]:
        directory = tmp_path/str(pid)
        directory.mkdir()
        (directory/'stat').write_text(f'{pid} ({name}) {state} {parent} 0 0')
    assert linux_other_cores(50, tmp_path) == ['clash-meta (PID 103)']


def test_linux_tun_preserves_explicit_node_resolver_and_source(tmp_path):
    from app.engine import parse_config
    runtime = Runtime(tmp_path)
    runtime.platform.info = platform_info('linux', 'x86_64')
    composed = {'config': {'proxies': [], 'dns': {'proxy-server-nameserver': ['https://my-dns.example/dns-query']},
                           'profile': {'store-selected': False}}}
    result = parse_config(runtime.prepare(composed, 17890, True))
    assert result['dns']['proxy-server-nameserver'] == ['https://my-dns.example/dns-query']
    assert not composed['config']['profile']['store-selected']
    assert result['profile']['store-selected']


def test_restore_only_still_valid_manual_groups(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path)
    writes = []
    def request(method, path, **kwargs):
        if method == 'GET':
            return {'proxies': {'Work / 工作': {'type': 'Selector', 'all': ['B'], 'now': 'B'},
                                'Automatic': {'type': 'URLTest', 'all': ['A']},
                                'Changed': {'type': 'Selector', 'all': ['C']}}}
        writes.append((path, kwargs['json']))
    monkeypatch.setattr(runtime, 'request', request)
    runtime.restore_selectors({'Work / 工作': 'B', 'Automatic': 'A', 'Changed': 'A', 'Removed': 'A'})
    assert writes == [('/proxies/Work%20%2F%20%E5%B7%A5%E4%BD%9C', {'name': 'B'})]
