import copy

from fastapi.testclient import TestClient

from server.api import build_app
from server.dns_summary import summarize_dns


def test_summary_never_exposes_credentials_url_paths_or_tokens():
    result = summarize_dns({'dns': {'enable': True, 'nameserver': [
        'https://user:secret@dns.example/private-token?key=hidden#Proxy',
        'https://dns.example/another-token', 'tls://[2606:4700:4700::1111]:853',
        '1.1.1.1#private-group', 'https://broken:invalid/', None,
    ]}})
    assert result == {'status': 'ok', 'nameservers': ['https://dns.example', 'tls://[2606:4700:4700::1111]:853', '1.1.1.1']}
    assert summarize_dns({}) == {'status': 'disabled', 'nameservers': []}
    assert summarize_dns({'dns': {'enable': True}})['status'] == 'unavailable'


def test_offline_summary_uses_prepared_selected_configuration_without_mutation(tmp_path, monkeypatch):
    app = build_app(tmp_path)
    core = app.state.runtime
    monkeypatch.setattr(core, 'alive', lambda: False)
    headers = {'X-Clash-Studio': '1'}
    with TestClient(app) as client:
        profile = client.post('/api/subscriptions', headers=headers, json={
            'title': 'DNS summary', 'source_type': 'file',
            'yaml': 'dns: {enable: true, nameserver: ["https://dns.example/private?token=secret"]}\nproxies: []\nproxy-groups: []\nrules: ["MATCH,REJECT"]',
        }).json()
        before = copy.deepcopy(app.state.store.get(profile['id']))
        response = client.get('/api/client/network/dns-summary', params={'profile_id': profile['id']}, headers=headers)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['source'] == 'selected' and value['profile_id'] == profile['id']
        assert value['nameservers'] == ['https://dns.example']
        assert app.state.store.get(profile['id']) == before
        assert not core.alive()


def test_running_summary_reads_applied_snapshot_even_if_another_profile_is_selected(tmp_path, monkeypatch):
    app = build_app(tmp_path)
    core = app.state.runtime
    headers = {'X-Clash-Studio': '1'}
    with TestClient(app) as client:
        core.directory.joinpath('active.yaml').write_text('dns: {enable: true, nameserver: [9.9.9.9]}\nproxies: []\nproxy-groups: []\nrules: ["MATCH,REJECT"]\n', encoding='utf-8')
        core.active = {'profile_id': 'running-a', 'hash': 'applied-hash'}
        with monkeypatch.context() as patch:
            patch.setattr(core, 'alive', lambda: True)
            response = client.get('/api/client/network/dns-summary?profile_id=selected-b', headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == {'status': 'ok', 'nameservers': ['9.9.9.9'], 'source': 'runtime', 'profile_id': 'running-a', 'config_hash': 'applied-hash'}
