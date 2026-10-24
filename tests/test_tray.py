from fastapi import HTTPException
from fastapi.testclient import TestClient
from server.api import build_app

HEADERS = {'X-Clash-Studio': '1'}


def test_tray_without_selection_and_validation(tmp_path):
    with TestClient(build_app(tmp_path)) as client:
        assert not client.get('/api/client/tray').json()['can_start']
        assert client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'toggle'}).status_code == 409
        assert client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'bad'}).status_code == 422
        assert client.post('/api/client/tray/action', json={'action': 'global'}).status_code == 403
        assert client.put('/api/client/tray/context', headers=HEADERS, json={'profile_id': 'missing'}).status_code == 404
        for mode in ('rule', 'global', 'direct'):
            response = client.post('/api/client/tray/action', headers=HEADERS, json={'action': mode})
            assert response.status_code == 200, response.text
            assert response.json()['routing_mode'] == mode
        response = client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'tun'})
        assert response.json()['proxy_mode'] == 'tun'
        assert not response.json()['running']
    with TestClient(build_app(tmp_path)) as client:
        state = client.get('/api/client/tray').json()
        assert state['proxy_mode'] == 'tun' and state['routing_mode'] == 'direct'


def test_tray_toggle_and_live_mode_rollback(tmp_path, monkeypatch):
    app = build_app(tmp_path)
    runtime = app.state.runtime
    running = {'value': False, 'owned': False, 'tun': False}
    calls = []
    monkeypatch.setattr(runtime, 'alive', lambda: running['value'])
    monkeypatch.setattr(runtime, 'status', lambda: {
        'running': running['value'], 'proxy': {'owned': running['owned']},
        'tun': {'enabled': running['tun']}, 'routing_mode': 'rule'})
    def apply(composed, profile, port, tun, stack):
        calls.append((profile['id'], port, tun, stack))
        running['value'] = True
        return runtime.status()
    def mode(value, stack):
        if value == 'tun':
            raise HTTPException(409, 'test elevation rejected')
        running['owned'] = value == 'system'
        return runtime.status()
    def stop(*args, **kwargs):
        running.update(value=False, owned=False, tun=False)
        return runtime.status()
    monkeypatch.setattr(runtime, 'apply', apply)
    monkeypatch.setattr(runtime, 'change_mode', mode)
    monkeypatch.setattr(runtime, 'stop', stop)
    with TestClient(app) as client:
        profile = client.post('/api/subscriptions', headers=HEADERS, json={
            'title': 'tray-test', 'source_type': 'file',
            'yaml': 'proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]\n'}).json()
        response = client.put('/api/client/tray/context', headers=HEADERS, json={'profile_id': profile['id']})
        assert response.status_code == 200, response.text
        assert client.get('/api/client/tray').json()['can_start']
        state = client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'toggle'}).json()
        assert state['enabled'] and calls[0][0] == profile['id']
        assert client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'tun'}).status_code == 409
        state = client.get('/api/client/tray').json()
        assert state['enabled'] and state['proxy_mode'] == 'system'
        state = client.post('/api/client/tray/action', headers=HEADERS, json={'action': 'toggle'}).json()
        assert not state['running'] and not state['enabled']
        assert len(calls) == 1
