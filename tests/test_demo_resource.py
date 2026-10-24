from pathlib import Path
import shutil
from fastapi.testclient import TestClient
from app import main


def test_packaged_demo_import_and_refresh(tmp_path, monkeypatch):
    # Resource root mimics vendor/ inside a clean portable distribution.
    resource=tmp_path/'vendor'
    (resource/'examples').mkdir(parents=True)
    source=Path(__file__).resolve().parents[1]/'vendor/examples/demo.yaml'
    shutil.copy2(source,resource/'examples/demo.yaml')
    monkeypatch.setattr(main,'ROOT',resource)
    with TestClient(main.create_app(tmp_path/'data')) as client:
        headers={'X-Clash-Studio':'1'}
        response=client.post('/api/subscriptions',headers=headers,json={'source_type':'demo','title':'demo-resource-test'})
        assert response.status_code==201,response.text
        profile=response.json()
        assert profile['proxy_count']>0 and not profile['preview']['errors']
        refreshed=client.post(f"/api/subscriptions/{profile['id']}/refresh",headers=headers,json={'revision':profile['revision']})
        assert refreshed.status_code==200,refreshed.text


def test_missing_demo_gives_actionable_error(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'ROOT',tmp_path/'missing-vendor')
    with TestClient(main.create_app(tmp_path/'data')) as client:
        response=client.post('/api/subscriptions',headers={'X-Clash-Studio':'1'},json={'source_type':'demo','title':'missing'})
        assert response.status_code==503
        assert '重新解压' in response.json()['detail']
