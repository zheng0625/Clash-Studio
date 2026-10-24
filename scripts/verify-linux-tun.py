"""Root-only integration harness; real TUN in two disposable network namespaces.

The client runs as an ordinary user. Only a temporary copy of Mihomo gets caps.
No personal subscriptions, desktop proxy or host routing are used.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]


def client(home, orphan=False):
    import httpx
    from fastapi import HTTPException
    from server.runtime import Runtime
    runtime = Runtime(home)
    composed = {'config': {'proxies': [], 'proxy-groups': [{'name': 'Egress', 'type': 'select', 'proxies': ['REJECT', 'DIRECT']}],
                           'rules': ['MATCH,Egress']}, 'errors': [], 'workspace_revision': 1}
    row = {'id': 'tun-integration', 'title': 'Isolated TUN test', 'revision': 1, 'enabled': True}
    try:
        assert os.geteuid() != 0 and runtime.elevation.ready
        if orphan:
            runtime.apply(composed, row, 17890, True)
            (home/'orphan-ready').write_text(str(runtime.process.pid))
            os._exit(0)
        runtime.apply(composed, row, 17890, False)
        runtime.request('PUT', '/proxies/Egress', json={'name': 'DIRECT'})
        previous_pid = runtime.process.pid
        ensure = runtime.elevation.ensure
        def cancel():
            raise HTTPException(409, 'test authorization cancelled')
        runtime.elevation.ensure = cancel
        try:
            runtime.apply(composed, row, 17890, True)
            raise AssertionError('Cancelled authorization unexpectedly succeeded')
        except HTTPException as error:
            assert error.status_code == 409
        assert runtime.process.pid == previous_pid and runtime.alive() and not runtime.active['tun']
        runtime.elevation.ensure = ensure
        runtime.change_mode('tun')
        assert runtime.process.pid != previous_pid
        assert runtime.request('GET', '/proxies')['proxies']['Egress']['now'] == 'DIRECT'
        assert socket.if_nametoindex('ClashStudio')
        with httpx.Client(trust_env=False, timeout=8) as connection:
            response = connection.get('http://203.0.113.1:18080/proof.txt')
            assert response.text == 'real-linux-tun-egress\n'
        # No DNS server runs at this address: a fake-IP reply proves DNS interception.
        labels = b''.join(bytes([len(p)])+p for p in [b'clash-studio', b'example', b'com'])+b'\0'
        query = struct.pack('!6H', 0x1234, 0x100, 1, 0, 0, 0)+labels+struct.pack('!2H', 1, 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(5)
            udp.sendto(query, ('10.203.0.1', 53))
            answer = udp.recv(4096)
        assert answer[:2] == b'\x12\x34' and struct.unpack_from('!H', answer, 6)[0] > 0
        assert b'\xc6\x13' in answer  # 198.19.0.0/16, separate from common router pools
        traffic = runtime.traffic()
        assert traffic['download'] > 0
        runtime.change_mode('manual')
        assert not runtime.active['tun']
        try:
            socket.if_nametoindex('ClashStudio')
            raise AssertionError('TUN interface survived disable')
        except OSError:
            pass
        runtime.change_mode('tun')
        runtime.stop()
        assert not runtime.alive()
        print(json.dumps({'unprivileged_file_capabilities': True, 'cancel_keeps_old_core': True,
            'plain_to_tun_restart': True, 'selector_preserved_after_restart': True, 'plain_http_through_tun': True, 'dns_hijack_fake_ip': True,
            'download_bytes': traffic['download'], 'tun_disable_and_reenable': True, 'normal_stop': True}))
    finally:
        runtime.stop(report=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', type=Path)
    parser.add_argument('--orphan', action='store_true')
    parser.add_argument('--user', default='clashbuild')
    args = parser.parse_args()
    if args.client:
        client(args.client, args.orphan)
        return
    assert os.geteuid() == 0, 'Network namespace setup requires root'
    account = pwd.getpwnam(args.user)
    prefix = 'clash-tun-'+str(os.getpid())
    names = [prefix+'-client', prefix+'-origin']
    home = Path(tempfile.mkdtemp(prefix=prefix))
    origin = None
    def run(*argv, **kw):
        return subprocess.run(argv, check=True, text=True, capture_output=True, **kw)
    try:
        home.chmod(0o755)
        (home/'bin').mkdir()
        binary = home/'bin/mihomo-linux-amd64'
        shutil.copy2(ROOT/'bin/mihomo-linux-amd64', binary)
        os.chown(home, account.pw_uid, account.pw_gid)
        run('setcap', 'cap_net_admin,cap_net_raw,cap_net_bind_service=ep', str(binary))
        (home/'proof.txt').write_text('real-linux-tun-egress\n')
        for name in names:
            run('ip', 'netns', 'add', name)
            run('ip', '-n', name, 'link', 'set', 'lo', 'up')
        run('ip', 'link', 'add', 'clashc'+str(os.getpid()), 'type', 'veth', 'peer', 'name', 'clasho'+str(os.getpid()))
        for name, iface, address in [(names[0], 'clashc'+str(os.getpid()), '10.203.0.2/24'), (names[1], 'clasho'+str(os.getpid()), '10.203.0.1/24')]:
            run('ip', 'link', 'set', iface, 'netns', name)
            run('ip', '-n', name, 'addr', 'add', address, 'dev', iface)
            run('ip', '-n', name, 'link', 'set', iface, 'up')
        run('ip', '-n', names[1], 'addr', 'add', '203.0.113.1/32', 'dev', 'lo')
        run('ip', '-n', names[0], 'route', 'add', 'default', 'via', '10.203.0.1')
        baseline = run('ip', '-n', names[0], '-j', 'rule').stdout
        origin = subprocess.Popen(['ip', 'netns', 'exec', names[1], sys.executable, '-m', 'http.server', '18080', '--bind', '203.0.113.1', '--directory', str(home)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(.3)
        command = ['ip', 'netns', 'exec', names[0], 'runuser', '-u', args.user, '--', sys.executable, '-B', str(Path(__file__).resolve()), '--client', str(home)]
        result = subprocess.run(command, text=True, capture_output=True, timeout=75)
        if result.returncode:
            print(result.stderr)
            print((home/'data/runtime/core.log').read_text()[-10000:] if (home/'data/runtime/core.log').exists() else '')
            raise RuntimeError('TUN integration failed')
        print(result.stdout.strip())
        assert run('ip', '-n', names[0], '-j', 'rule').stdout == baseline
        run(*command, '--orphan', timeout=30)
        assert (home/'orphan-ready').exists()
        for _ in range(60):
            links = json.loads(run('ip', '-n', names[0], '-j', 'link').stdout)
            if not any(link['ifname'] == 'ClashStudio' for link in links):
                break
            time.sleep(.1)
        else:
            raise AssertionError('TUN survived abrupt backend exit')
        assert run('ip', '-n', names[0], '-j', 'rule').stdout == baseline
        print(json.dumps({'normal_stop_restores_rules': True, 'abrupt_backend_exit_removes_tun_and_rules': True}))
    finally:
        if origin:
            origin.terminate()
            origin.wait(timeout=5)
        for name in names:
            subprocess.run(['ip', 'netns', 'del', name], capture_output=True)
        shutil.rmtree(home)


if __name__ == '__main__':
    main()
