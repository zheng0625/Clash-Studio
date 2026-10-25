"""Verify GNOME settings, real GIO routing, core counters and restoration."""
import json
from pathlib import Path
import sys

if len(sys.argv)>1 and sys.argv[1]=='--gio':
    import gi
    gi.require_version('Gio','2.0')
    from gi.repository import Gio
    url=sys.argv[2]
    proxies=Gio.ProxyResolver.get_default().lookup(url,None)
    assert any(p.startswith('http://127.0.0.1:') for p in proxies),proxies
    client=Gio.SocketClient.new();client.set_timeout(8)
    connection=client.connect_to_uri(url,80,None)
    connection.get_output_stream().write_all(b'GET / HTTP/1.0\r\nHost: gnome-test\r\n\r\n',None)
    data=bytearray()
    while True:
        block=connection.get_input_stream().read_bytes(65536,None).get_data()
        if not block:break
        data.extend(block)
    connection.close(None)
    assert b'gnome-proxy-egress' in data
    print(json.dumps({'gnome_resolver':True,'gio_request':True,'bytes':len(data)}))
    raise SystemExit(0)

import http.server
import socket
import subprocess
import tempfile
import threading
import time

package=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(package),str(package/'vendor')]
from fastapi.testclient import TestClient
from server.api import build_app
from server.gnome_proxy import GnomeProxy

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'gnome-proxy-egress'*4096
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

with tempfile.TemporaryDirectory(prefix='clash-gnome-') as temporary:
    proxy=GnomeProxy(temporary);before=proxy.read()
    origin=http.server.ThreadingHTTPServer(('0.0.0.0',0),Handler)
    threading.Thread(target=origin.serve_forever,daemon=True).start()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    try:
        with TestClient(build_app(package,data_dir=Path(temporary))) as client:
            def call(path,method='GET',body=None):
                response=client.request(method,path,json=body,headers={'X-Clash-Studio':'1'});assert response.is_success,response.text;return response.json()
            assert call('/api/client/platform')['capabilities']['system_proxy']
            profile=call('/api/subscriptions','POST',{'title':'GNOME local verification','source_type':'file','yaml':'proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]\n'})
            workspace=call('/api/client/workspace')
            state=call('/api/client/runtime/apply','POST',{'profile_id':profile['id'],'profile_revision':profile['revision'],'workspace_revision':workspace['revision'],'mixed_port':port})
            assert state['proxy']['owned']
            base=call('/api/client/runtime/connections')
            gio=json.loads(subprocess.check_output(['/usr/bin/python3','-I',str(Path(__file__).resolve()),'--gio',f'http://192.168.88.196:{origin.server_port}/'],text=True,timeout=15))
            time.sleep(.3)
            traffic=call('/api/client/runtime/connections')
            delta=traffic['downloadTotal']-base['downloadTotal']
            assert delta>0,traffic
            assert not call('/api/client/runtime/stop','POST',{})['running']
            assert proxy.read()==before and not proxy.path.exists()
            call('/api/client/tray/context','PUT',{'profile_id':profile['id'],'proxy_mode':'system','mixed_port':port})
            assert call('/api/client/tray/action','POST',{'action':'toggle'})['enabled']
            assert proxy.status()['owned'] and proxy.read()['org.gnome.system.proxy/mode']=="'manual'"
            assert not call('/api/client/tray/action','POST',{'action':'toggle'})['enabled']
            assert proxy.read()==before and not proxy.path.exists()
            print(json.dumps({'tray_toggle_capture_and_release':True,**gio,'system_proxy_owned':True,'core_download_delta':delta,'previous_settings_restored':True}))
    finally:
        origin.shutdown();origin.server_close()
        assert proxy.read()==before,'GNOME settings restoration needs attention'
