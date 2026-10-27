"""Resume the selected published profile via the running desktop's local API.

Read the per-process desktop nonce in memory; never print or persist it.
"""
import json
import os
from pathlib import Path
import sys
import urllib.request

package=Path(sys.argv[1]).resolve()
for directory in Path('/proc').iterdir():
    if not directory.name.isdecimal():continue
    try:
        if directory.stat().st_uid!=os.getuid():continue
        args=(directory/'cmdline').read_bytes().decode().split('\0')
        if str(package/'run.py') not in args or '--desktop' not in args:continue
        env=dict(item.split('=',1) for item in (directory/'environ').read_bytes().decode().split('\0') if '=' in item)
        token=env['CLASH_STUDIO_DESKTOP_TOKEN']
        port=int(args[args.index('--port')+1])
        break
    except (OSError,KeyError,ValueError):continue
else:raise SystemExit('Running desktop backend was not found')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(path,body=None):
    headers={'X-Clash-Studio':'1','X-Clash-Desktop-Token':token,'Content-Type':'application/json'}
    request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers=headers,data=None if body is None else json.dumps(body).encode())
    with opener.open(request,timeout=30) as response:return json.load(response)
state=call('/api/client/tray')
if not state['enabled']:
    if not state['can_start']:raise SystemExit('Select a subscription in the main window first')
    state=call('/api/client/tray/action',{'action':'toggle'})
runtime=call('/api/client/runtime')
print(json.dumps({'running':runtime['running'],'system_proxy_owned':runtime['proxy']['owned'],'proxy_mode':state['proxy_mode'],'routing_mode':state['routing_mode']}))
