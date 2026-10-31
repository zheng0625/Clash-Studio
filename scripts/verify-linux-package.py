"""End-to-end package check with its own Python/core and local HTTP origin."""
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import httpx

package=Path(sys.argv[1]).resolve()
def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'linux-package-egress')
    def log_message(self,*args):pass
origin=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=origin.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='clash-linux-verify-') as temporary:
    data=Path(temporary)/'用户数据';backend_port=port();mixed=port()
    log=(Path(temporary)/'backend.log').open('w+')
    process=subprocess.Popen([str(package/'runtime/python/bin/python3'),'-I','-B',str(package/'run.py'),'--no-window','--port',str(backend_port),'--data-dir',str(data)],cwd=temporary,stdout=log,stderr=subprocess.STDOUT,env={**os.environ, 'XDG_CURRENT_DESKTOP': 'isolated-package-test'})
    client=httpx.Client(base_url=f'http://127.0.0.1:{backend_port}',trust_env=False,timeout=15,headers={'X-Clash-Studio':'1'})
    def call(path,method='GET',body=None):
        response=client.request(method,path,json=body);response.raise_for_status();return response.json()
    try:
        for attempt in range(80):
            try:info=call('/api/client/info');break
            except httpx.HTTPError:time.sleep(.1)
        else:raise RuntimeError('Packaged backend failed to start')
        assert info['version']=='1.3.0' and info['platform']=='linux-x64' and info['paths']['data']==str(data)
        profile=call('/api/subscriptions','POST',{'source_type':'file','title':'Linux package local test','yaml':'proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]\n'})
        workspace=call('/api/client/workspace')
        call('/api/client/settings','PUT',{'mixed_port': mixed})
        state=call('/api/client/runtime/apply','POST',{'profile_id':profile['id'],'profile_revision':profile['revision'],'workspace_revision':workspace['revision'],'mixed_port':mixed,'proxy_mode':'manual'})
        assert state['running'] and not state['proxy']['owned']
        with httpx.Client(proxy=f'http://127.0.0.1:{mixed}',trust_env=False,timeout=5) as proxy:
            assert proxy.get(f'http://127.0.0.1:{origin.server_port}/').text=='linux-package-egress'
        for mode in ('rule','global','direct'):
            assert call('/api/client/runtime/routing-mode','PUT',{'mode':mode})['routing_mode']==mode
        assert not call('/api/client/runtime/stop','POST',{})['running']
        call('/api/client/tray/context','PUT',{'profile_id':profile['id'], 'mixed_port': mixed})
        assert call('/api/client/tray/action','POST',{'action':'toggle'})['enabled']
        assert not call('/api/client/tray/action','POST',{'action':'toggle'})['running']
        call('/api/shutdown','POST',{});process.wait(10)
        print(json.dumps({'platform':info['platform'],'bundled_python':True,'bundled_core':True,'local_proxy_request':True,'routing_modes':3,'tray_manual_toggle':True,'clean_exit':process.returncode==0},ensure_ascii=False))
    finally:
        if process.poll() is None:process.terminate();process.wait(10)
        client.close();log.close();origin.shutdown()
