"""Assemble the Linux desktop and a relocatable Ubuntu Python runtime."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[1]
NAME='ClashStudio-1.0-linux-x64'
OUT=ROOT/'artifacts/releases'/NAME
if sys.platform!='linux' or OUT.exists():
    raise SystemExit('Build on Linux with a new output path')
OUT.mkdir(parents=True)
shutil.copy2(ROOT/'src-tauri/target/release/clash-studio',OUT/'ClashStudio')
for folder in ['server','vendor/app','vendor/examples','frontend/dist','licenses','docs']:
    shutil.copytree(ROOT/folder,OUT/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ['run.py','LICENSE','THIRD_PARTY_NOTICES.md']:
    shutil.copy2(ROOT/name,OUT/name)
shutil.copytree(ROOT/'src-tauri/icons',OUT/'icons')
(OUT/'bin').mkdir()
for name in ['mihomo-linux-amd64','linux-core-source.json']:
    shutil.copy2(ROOT/'bin'/name,OUT/'bin'/name)
shutil.copytree(ROOT/'bin/geodata',OUT/'bin/geodata')
runtime=OUT/'runtime/python'
(runtime/'bin').mkdir(parents=True)
shutil.copy2(Path(sys.executable).resolve(),runtime/'bin/python3')
shutil.copy2('/usr/share/doc/python3.10/copyright',runtime/'Python-COPYRIGHT.txt')
stdlib=Path(sysconfig.get_path('stdlib'))
shutil.copytree(stdlib,runtime/'lib'/stdlib.name,symlinks=False,ignore=shutil.ignore_patterns('site-packages','dist-packages','__pycache__','*.pyc','test','tests','idlelib','tkinter','turtledemo','ensurepip'))
python=runtime/'bin/python3'
sites=json.loads(subprocess.check_output([str(python),'-I','-c','import site,json;print(json.dumps(site.getsitepackages()))']))
site=next(Path(p) for p in sites if Path(p).is_relative_to(runtime))
site.mkdir(parents=True,exist_ok=True)
todo=['fastapi','uvicorn','httpx','ruamel.yaml'];seen=set();versions=[]
while todo:
    dist=metadata.distribution(todo.pop());name=dist.metadata['Name']
    if name.lower() in seen:continue
    seen.add(name.lower());versions.append(name+'=='+dist.version)
    for item in dist.requires or []:
        requirement=Requirement(item)
        if requirement.marker is None or requirement.marker.evaluate({'extra':''}):todo.append(requirement.name)
    for relative in dist.files or []:
        source=Path(dist.locate_file(relative)).resolve()
        if '__pycache__' in source.parts or source.suffix=='.pyc' or not source.is_file():continue
        if '..' in relative.parts:continue
        target=site/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
subprocess.run([str(python),'-I','-c','import fastapi,uvicorn,httpx,ruamel.yaml,ssl,sqlite3;print("Bundled Python imports passed")'],check=True)
(OUT/'requirements.lock.txt').write_text('\n'.join(sorted(versions))+'\n')
(OUT/'portable.json').write_text(json.dumps({'version':'1.0.0','architecture':'linux-x64','data':'data'},indent=2)+'\n')
for name,body in [('Start.sh','exec "$root/ClashStudio" "$@"'),('Stop.sh','exec "$root/ClashStudio" --quit "$@"')]:
    (OUT/name).write_text('#!/bin/sh\nset -eu\nroot=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'+body+'\n');(OUT/name).chmod(0o755)
shutil.copy2(ROOT/'docs/linux-preview.md',OUT/'Linux测试说明.md')
source=OUT/'source/ClashStudio-source.zip';source.parent.mkdir()
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
    for folder in ['server','vendor/app','vendor/examples','frontend/src','frontend/public','src-tauri/src','src-tauri/capabilities','src-tauri/icons','scripts','tests','docs']:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':archive.write(path,path.relative_to(ROOT))
    for name in ['run.py','src-tauri/Cargo.toml','src-tauri/Cargo.lock','src-tauri/tauri.conf.json','src-tauri/build.rs','frontend/package.json','frontend/pnpm-lock.yaml','frontend/index.html','frontend/tsconfig.json','frontend/vite.config.ts','LICENSE']:
        archive.write(ROOT/name,name)
entries=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.rglob('*')) if p.is_file()]
(OUT/'manifest.json').write_text(json.dumps({'files':entries,'platform':'linux-x64','baseline':'Ubuntu 22.04'},indent=2)+'\n')
archive=OUT.parent/(NAME+'.tar.gz')
with tarfile.open(archive,'w:gz') as tar:tar.add(OUT,arcname=NAME)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name+'.sha256').write_text(digest+'  '+archive.name+'\n')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest}))
