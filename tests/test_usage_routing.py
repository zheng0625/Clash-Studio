from conftest import free_mixed_port
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.usage import subscription_usage
from app.engine import parse_config
from server.api import build_app
from server.runtime import Runtime


@pytest.mark.parametrize('raw,expected', [
    ('upload=10; download=30; total=100', (40,100,60,40)),
    ('upload=100;download=50;total=100', (150,100,0,100)),
    ('upload=0;download=0;total=100', (0,100,100,0)),
    ('upload=10;download=30;total=0', (40,None,None,None)),
])
def test_usage(raw, expected):
    result=subscription_usage(json.dumps({'subscription-userinfo':raw}))
    assert tuple(result[k] for k in ('used','total','remaining','percent')) == expected


@pytest.mark.parametrize('raw', ['', 'upload=-1;download=0;total=10',
    'upload=NaN;download=0;total=10','upload=1;download=2',
    'upload=1;upload=2;download=0;total=10','upload=9999999999999999;download=1;total=10'])
def test_invalid_usage_is_unknown(raw):
    assert subscription_usage({'subscription-userinfo':raw}) is None


def test_usage_exposed_in_summary_and_refresh(tmp_path, monkeypatch):
    from app import main
    config='proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]\n'
    quota={'subscription-userinfo':'upload=10;download=30;total=100'}
    monkeypatch.setattr(main,'fetch_source',lambda url:(config,quota))
    with TestClient(build_app(tmp_path)) as client:
        headers={'X-Clash-Studio':'1'}
        imported=client.post('/api/subscriptions',headers=headers,json={'title':'quota-test','source_type':'url','source_url':'https://example.com/test'}).json()
        assert imported['usage']['used']==40
        assert client.get('/api/subscriptions').json()[0]['usage']==imported['usage']
        quota['subscription-userinfo']='upload=20;download=40;total=100'
        refreshed=client.post('/api/subscriptions/'+imported['id']+'/refresh',headers=headers,json={'revision':imported['revision']})
        assert refreshed.status_code==200,refreshed.text
        assert refreshed.json()['usage']['remaining']==40
        assert client.put('/api/client/runtime/routing-mode',headers=headers,json={'mode':'invalid'}).status_code==422
        assert client.put('/api/client/runtime/routing-mode',headers=headers,json={'mode':'global'}).json()['routing_mode']=='global'


def test_real_core_routing_modes_and_persistence(tmp_path):
    root=Path(__file__).resolve().parents[1]
    runtime=Runtime(tmp_path,root)
    composed={'config':{'proxies':[],'proxy-groups':[{'name':'Work','type':'select','proxies':['DIRECT','REJECT']}], 'rules':['MATCH,REJECT']},'errors':[],'workspace_revision':1}
    row={'id':'routing-test','title':'routing-test','enabled':True,'revision':1}
    mixed=free_mixed_port()
    before=runtime.proxy.status()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'local-mode-test')
        def log_message(self,*args):
            pass
    origin=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=origin.serve_forever,daemon=True).start()
    try:
        runtime.change_routing_mode('direct')
        runtime.apply(composed,row,mixed,False,'mixed')
        core_pid=runtime.process.pid
        for mode in ('rule','global','direct'):
            state=runtime.change_routing_mode(mode)
            assert runtime.process.pid==core_pid and runtime.alive()
            assert state['routing_mode']==mode
            assert runtime.request('GET','/configs')['mode']==mode
            assert parse_config((runtime.directory/'active.yaml').read_text(encoding='utf-8'))['mode']==mode
        assert 'GLOBAL' in runtime.request('GET','/proxies')['proxies']
        runtime.request('PUT','/proxies/GLOBAL',json={'name':'REJECT'})
        for mode in ('rule','global','direct'):
            runtime.change_routing_mode(mode)
            with httpx.Client(proxy=f'http://127.0.0.1:{mixed}',trust_env=False,timeout=3) as client:
                response=client.get(f'http://127.0.0.1:{origin.server_port}/')
                assert (response.status_code==200)==(mode=='direct')
        runtime.apply(composed,row,mixed,False,'mixed')
        assert runtime.request('GET','/configs')['mode']=='direct'
        assert runtime.proxy.status()==before
        runtime.stop()
        restored=Runtime(tmp_path,root)
        assert restored.routing_mode=='direct'
        restored.stop()
    finally:
        runtime.stop()
        origin.shutdown()
        origin.server_close()


def test_unconfirmed_mode_does_not_save(tmp_path,monkeypatch):
    runtime=Runtime(tmp_path)
    monkeypatch.setattr(runtime,'alive',lambda:True)
    monkeypatch.setattr(runtime,'request',lambda method,path,**kw:{'mode':'rule'})
    with pytest.raises(HTTPException):
        runtime.change_routing_mode('global')
    assert not runtime.routing_path.exists()
    assert runtime.routing_mode=='rule'
