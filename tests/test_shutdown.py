from conftest import free_mixed_port
import socket
import time
from pathlib import Path
from fastapi.testclient import TestClient
from server.api import build_app
from server.runtime import Runtime


def test_prepare_exit_restores_before_blocking_new_mutations(tmp_path,monkeypatch):
    app=build_app(tmp_path)
    restored=[]
    monkeypatch.setattr(app.state.runtime.proxy,'restore',lambda:restored.append(time.monotonic()) or {'restored':True})
    with TestClient(app) as client:
        headers={'X-Clash-Studio':'1'}
        response=client.post('/api/client/prepare-exit',headers=headers,json={})
        assert response.status_code==200 and response.json()['restored']
        assert restored
        assert client.put('/api/client/runtime/routing-mode',headers=headers,json={'mode':'global'}).status_code==503
        assert client.get('/api/client/runtime').status_code==200
    assert len(restored)>=2


def test_fast_exit_stops_real_core_without_network_sampling(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1]
    runtime=Runtime(tmp_path,root)
    composed={'config':{'proxies':[],'proxy-groups':[],'rules':['MATCH,DIRECT']},'errors':[],'workspace_revision':1}
    row={'id':'shutdown','title':'shutdown','enabled':True,'revision':1}
    port=free_mixed_port()
    try:
        runtime.apply(composed,row,port,False,'mixed')
        process=runtime.process
        restored=[]
        monkeypatch.setattr(runtime.proxy,'restore',lambda:restored.append(True))
        monkeypatch.setattr(runtime,'traffic',lambda:(_ for _ in ()).throw(AssertionError('Exit should not wait for sampling')))
        start=time.monotonic()
        runtime.stop(final_sample=False,report=False)
        elapsed=time.monotonic()-start
        assert restored and process.poll() is not None
        assert elapsed<2.5
    finally:
        runtime.stop(final_sample=False,report=False)
