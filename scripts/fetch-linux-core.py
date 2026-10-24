"""Fetch the pinned official Linux core and record its provenance."""
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

root=Path(__file__).resolve().parents[1]
version='v1.19.33'
request=urllib.request.Request(f'https://api.github.com/repos/MetaCubeX/mihomo/releases/tags/{version}',headers={'User-Agent':'ClashStudio-build'})
with urllib.request.urlopen(request,timeout=90) as response:
    release=json.load(response)
names=[f'mihomo-linux-amd64-compatible-{version}.gz',f'mihomo-linux-amd64-{version}.gz']
asset=next(a for name in names for a in release['assets'] if a['name']==name)
with urllib.request.urlopen(asset['browser_download_url'],timeout=180) as response:
    packed=response.read()
digest=hashlib.sha256(packed).hexdigest()
if asset.get('digest'):
    assert asset['digest']=='sha256:'+digest,'Upstream digest mismatch'
binary=root/'bin/mihomo-linux-amd64'
binary.write_bytes(gzip.decompress(packed));binary.chmod(0o755)
(root/'bin/linux-core-source.json').write_text(json.dumps({'version':version,'url':asset['browser_download_url'],'download_sha256':digest,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'upstream_digest':asset.get('digest')},indent=2)+'\n')
print(binary)
