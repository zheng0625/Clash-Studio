from conftest import free_mixed_port
import shutil
import socket
from pathlib import Path

from fastapi.testclient import TestClient
from server.api import build_app
from server.platforms import core_binary

HEADERS = {'X-Clash-Studio': '1'}
CONFIG = '''proxy-groups:
  - {name: '手动 / Egress', type: select, proxies: [REJECT, DIRECT]}
  - {name: Automatic, type: url-test, proxies: [DIRECT], url: 'http://127.0.0.1:1', interval: 86400}
rules: ['MATCH,手动 / Egress']
'''


def test_offline_choices_persist_restore_and_reject_stale(tmp_path):
    source = core_binary(Path(__file__).resolve().parents[1])
    (tmp_path / 'bin').mkdir()
    shutil.copy2(source, tmp_path / 'bin' / source.name)
    app = build_app(tmp_path)
    with TestClient(app) as client:
        profile = client.post('/api/subscriptions', headers=HEADERS,
                              json={'title': 'offline', 'source_type': 'file', 'yaml': CONFIG}).json()
        other = client.post('/api/subscriptions', headers=HEADERS,
                            json={'title': 'other', 'source_type': 'file', 'yaml': CONFIG}).json()
        catalog = client.get('/api/client/proxy-catalog', params={'profile_id': profile['id']}).json()
        body = {'profile_id': profile['id'], 'profile_revision': catalog['profile_revision'],
                'workspace_revision': catalog['workspace_revision'], 'group': '手动 / Egress', 'name': 'DIRECT'}
        assert client.put('/api/client/proxy-selection', headers=HEADERS, json={**body, 'profile_revision': -1}).status_code == 409
        assert client.put('/api/client/proxy-selection', headers=HEADERS, json={**body, 'group': 'Automatic'}).status_code == 422
        assert client.put('/api/client/proxy-selection', headers=HEADERS, json={**body, 'name': 'missing'}).status_code == 422
        saved = client.put('/api/client/proxy-selection', headers=HEADERS, json=body)
        assert saved.status_code == 200 and not saved.json()['live']
        assert not app.state.runtime.alive()
        assert not (tmp_path / 'data/probe').exists()
        assert client.get('/api/client/proxy-catalog', params={'profile_id': other['id']}).json()['proxies']['手动 / Egress']['now'] == 'REJECT'
    # Reload the complete backend, then start the real bundled core.
    with TestClient(build_app(tmp_path)) as client:
        assert client.get('/api/client/proxy-catalog', params={'profile_id': profile['id']}).json()['proxies']['手动 / Egress']['now'] == 'DIRECT'
        port = free_mixed_port()
        apply = {k: body[k] for k in ('profile_id', 'profile_revision', 'workspace_revision')}
        apply.update(mixed_port=port, proxy_mode='manual')
        started = client.post('/api/client/runtime/apply', headers=HEADERS, json=apply)
        assert started.status_code == 200, started.text
        assert client.get('/api/client/runtime/proxies').json()['proxies']['手动 / Egress']['now'] == 'DIRECT'
        switched = client.put('/api/client/proxy-selection', headers=HEADERS, json={**body, 'name': 'REJECT'})
        assert switched.status_code == 200 and switched.json()['live']
        client.post('/api/client/runtime/stop', headers=HEADERS, json={})
        assert client.post('/api/client/runtime/apply', headers=HEADERS, json=apply).status_code == 200
        assert client.get('/api/client/runtime/proxies').json()['proxies']['手动 / Egress']['now'] == 'REJECT'


def test_installed_windows_data_path(tmp_path):
    from server.paths import default_data_dir
    (tmp_path / 'installed.json').touch()
    external = tmp_path / 'local'
    assert default_data_dir(tmp_path, platform='win32', env={'LOCALAPPDATA': str(external)}) == external / 'ClashStudio'
    assert default_data_dir(tmp_path, platform='win32', env={'CLASH_STUDIO_DATA': str(external)}) == external
