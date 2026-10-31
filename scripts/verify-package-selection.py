"""Exercise bundled Python, offline selection, core start and real local traffic."""
import http.server
import json
import os
from pathlib import Path
import socket
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import httpx

package = Path(sys.argv[1]).resolve()
python = package / ('runtime/python/python.exe' if os.name == 'nt' else 'runtime/python/bin/python3')


def free_port():
    for _ in range(1000):
        number = 20000 + secrets.randbelow(29000)
        with socket.socket() as tcp, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            try:
                tcp.bind(('127.0.0.1', number))
                udp.bind(('127.0.0.1', number))
                return number
            except OSError:
                continue
    raise RuntimeError('No free loopback TCP/UDP port')


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'packaged-selection-egress')

    def log_message(self, *args):
        pass


origin = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=origin.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix='clash-selection-') as temporary:
    data = Path(temporary) / 'user data'
    port, mixed = free_port(), free_port()
    log = (Path(temporary) / 'backend.log').open('w+')
    process = subprocess.Popen([str(python), '-I', '-B', str(package / 'run.py'), '--no-window', '--port', str(port), '--data-dir', str(data)],
                               cwd=temporary, stdout=log, stderr=subprocess.STDOUT)
    client = httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=15, headers={'X-Clash-Studio': '1'})

    def call(path, method='GET', body=None):
        response = client.request(method, path, json=body)
        response.raise_for_status()
        return response.json()

    try:
        for _ in range(100):
            try:
                info = call('/api/client/info')
                break
            except httpx.HTTPError:
                time.sleep(.1)
        else:
            raise AssertionError('Bundled backend did not start')
        assert info['version'] == '1.3.0'
        profile = call('/api/subscriptions', 'POST', {'title': 'Packaged offline selector', 'source_type': 'file',
                       'yaml': 'proxy-groups:\n  - {name: Manual, type: select, proxies: [REJECT, DIRECT]}\nrules: ["MATCH,Manual"]\n'})
        catalog = call('/api/client/proxy-catalog?profile_id=' + profile['id'])
        choice = {k: catalog[k] for k in ('profile_revision', 'workspace_revision')}
        choice.update(profile_id=profile['id'], group='Manual', name='DIRECT')
        assert not call('/api/client/proxy-selection', 'PUT', choice)['live']
        assert not call('/api/client/runtime')['running']
        apply = {k: choice[k] for k in ('profile_id', 'profile_revision', 'workspace_revision')}
        apply.update(mixed_port=mixed, proxy_mode='manual')
        assert call('/api/client/runtime/apply', 'POST', apply)['running']
        assert call('/api/client/runtime/proxies')['proxies']['Manual']['now'] == 'DIRECT'
        with httpx.Client(proxy=f'http://127.0.0.1:{mixed}', trust_env=False, timeout=5) as traffic:
            assert traffic.get(f'http://127.0.0.1:{origin.server_port}').text == 'packaged-selection-egress'
        durations = []
        for name in ['REJECT', 'DIRECT'] * 5:
            start = time.perf_counter()
            assert call('/api/client/proxy-selection', 'PUT', {**choice, 'name': name})['live']
            durations.append(round((time.perf_counter() - start) * 1000, 2))
        assert not call('/api/client/runtime/stop', 'POST', {})['running']
        assert call('/api/client/runtime/apply', 'POST', apply)['running']
        assert call('/api/client/runtime/proxies')['proxies']['Manual']['now'] == 'DIRECT'
        assert not call('/api/client/runtime/stop', 'POST', {})['running']
        call('/api/shutdown', 'POST', {})
        process.wait(10)
        assert process.returncode == 0
        print(json.dumps({'version': info['version'], 'platform': info['platform'], 'offline_choice': True,
                          'real_core_applies_choice': True, 'local_proxy_http': 200, 'restart_restores_choice': True,
                          'live_switch_ms': durations, 'clean_exit': True}))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(10)
        log.close()
        client.close()
        origin.shutdown()
