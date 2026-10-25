"""Real desktop-resolved HTTPS request; no explicit proxy argument or secrets."""
import json
import sys
from urllib.parse import urlsplit
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio
url=sys.argv[1] if len(sys.argv)>1 else 'https://example.com/'
target=urlsplit(url)
proxies=Gio.ProxyResolver.get_default().lookup(url,None)
assert any('127.0.0.1:' in proxy for proxy in proxies),'Desktop proxy is not configured'
client=Gio.SocketClient.new();client.set_timeout(12);client.set_tls(target.scheme=='https')
stream=client.connect_to_uri(url,443 if target.scheme=='https' else 80,None)
request=f'GET {target.path or "/"} HTTP/1.0\r\nHost: {target.hostname}\r\nConnection: close\r\n\r\n'.encode()
stream.get_output_stream().write_all(request,None)
data=stream.get_input_stream().read_bytes(8192,None).get_data()
stream.close(None)
status=data.split(b'\r\n',1)[0].decode('ascii','replace')
assert ' 200 ' in status,status
print(json.dumps({'desktop_proxy_used':True,'https_tls_verified':True,'status':status,'received_bytes':len(data)}))
