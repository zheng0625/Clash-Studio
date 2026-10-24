"""Assemble a clean Windows x64 release from the already built desktop binary.

Run with the development venv Python; no downloads or user data are included.
Existing release directories are never overwritten.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import zipfile
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ClashStudio-0.5.17-portable-windows-x64'
RELEASES = ROOT / 'artifacts' / 'releases'
OUT = RELEASES / NAME
ZIP = RELEASES / (NAME + '.zip')


def copy(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def digest(path: Path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def distributions():
    todo = ['fastapi', 'uvicorn', 'httpx', 'ruamel.yaml']
    seen = set()
    result = []
    while todo:
        dist = metadata.distribution(todo.pop())
        name = dist.metadata['Name'].lower()
        if name in seen:
            continue
        seen.add(name)
        result.append(dist)
        for value in dist.requires or []:
            requirement = Requirement(value)
            if not requirement.marker or requirement.marker.evaluate({'extra': ''}):
                todo.append(requirement.name)
    return sorted(result, key=lambda dist: dist.metadata['Name'].lower())


def main():
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 12):
        raise SystemExit('Build using the existing Windows x64 Python 3.12 development venv.')
    if OUT.exists() or ZIP.exists():
        raise SystemExit('Release path already exists. Keep it and select a new release name.')
    required = ['vendor/examples/demo.yaml', 'bin/mihomo-windows-amd64-compatible.exe', 'bin/wintun.dll', 'bin/geodata/source.json',
                *['bin/geodata/' + name for name in ['Country.mmdb', 'geoip.dat', 'geosite.dat', 'ASN.mmdb']]]
    for name in required:
        if not (ROOT / name).is_file() or (ROOT / name).stat().st_size < 16:
            raise SystemExit('Required bundled resource missing: ' + name)
    expected = {item['name']: item['sha256'] for item in json.loads((ROOT / 'bin/geodata/source.json').read_text(encoding='utf-8-sig'))['files']}
    for name in ['Country.mmdb', 'geoip.dat', 'geosite.dat', 'ASN.mmdb']:
        if digest(ROOT / 'bin/geodata' / name).lower() != expected.get(name, '').lower():
            raise SystemExit('Bundled GeoData checksum mismatch: ' + name)
    OUT.mkdir(parents=True)
    copy(ROOT / 'src-tauri/target/release/clash-studio.exe', OUT / 'ClashStudio.exe')
    copy(ROOT / 'run.py', OUT / 'run.py')
    for folder in ['server', 'vendor/app', 'vendor/examples', 'frontend/dist']:
        shutil.copytree(ROOT / folder, OUT / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    runtime = OUT / 'runtime/python'
    base = Path(sys.base_prefix)
    for name in ['python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt']:
        copy(base / name, runtime / name)
    for name in ['vcruntime140.dll', 'vcruntime140_1.dll']:
        copy(base / name, OUT / name)
    shutil.copytree(base / 'DLLs', runtime / 'DLLs', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(base / 'Lib', runtime / 'Lib', ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip'))
    (runtime / 'python312._pth').write_text('.\nDLLs\nLib\nLib/site-packages\nimport site\n', encoding='ascii')
    versions = []
    for dist in distributions():
        source_root = Path(dist.locate_file('')).resolve()
        versions.append(f"{dist.metadata['Name']}=={dist.version}")
        for relative in dist.files or []:
            source = Path(dist.locate_file(relative)).resolve()
            if not source.is_relative_to(source_root) or '__pycache__' in source.parts or source.suffix == '.pyc':
                continue
            if source.is_file():
                copy(source, runtime / 'Lib/site-packages' / source.relative_to(source_root))
    (OUT / 'requirements.lock.txt').write_text('\n'.join(versions) + '\n', encoding='utf-8')

    for name in ['mihomo-windows-amd64-compatible.exe', 'wintun.dll', 'source.json']:
        copy(ROOT / 'bin' / name, OUT / 'bin' / name)
    files = []
    for name in ['Country.mmdb', 'geoip.dat', 'geosite.dat', 'ASN.mmdb']:
        destination = OUT / 'bin/geodata' / name
        copy(ROOT / 'bin/geodata' / name, destination)
        if digest(destination).lower() != expected[name].lower():
            raise SystemExit('Resource changed during assembly: ' + name)
        # This is a clean database seed, never a copy of the development data directory.
        copy(destination, OUT / 'data/runtime' / name)
        files.append({'name': name, 'sha256': digest(destination), 'bytes': destination.stat().st_size})
    (OUT / 'bin/geodata/source.json').write_text(json.dumps({'origin': 'Local bundled snapshot; not claimed latest', 'upstream': 'https://github.com/MetaCubeX/meta-rules-dat', 'files': files}, indent=2), encoding='utf-8')
    copy(ROOT / 'bin/wintun-package/wintun/LICENSE.txt', OUT / 'licenses/Wintun-LICENSE.txt')
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md']:
        copy(ROOT / name, OUT / name)
    copy(ROOT / '六项优化说明.md', OUT / '六项优化说明.md')
    copy(ROOT / '0.5.17发布说明.md', OUT / '0.5.17发布说明.md')
    (OUT / 'portable.json').write_text(json.dumps({'version': '0.5.17', 'architecture': 'windows-x64', 'python': '.'.join(map(str, sys.version_info[:3])), 'data': 'data', 'webview2': 'system runtime required'}, indent=2), encoding='utf-8')
    (OUT / '管理员启动.cmd').write_text('@echo off\r\npowershell.exe -NoProfile -Command "Start-Process -FilePath \'%~dp0ClashStudio.exe\' -WorkingDirectory \'%~dp0\' -Verb RunAs"\r\n', encoding='utf-8')
    (OUT / '恢复系统代理.cmd').write_text('@echo off\r\n"%~dp0runtime\\python\\python.exe" -I -B "%~dp0run.py" --restore-proxy\r\npause\r\n', encoding='utf-8')
    (OUT / '使用说明.txt').write_text('''Clash Studio 0.5.17 Portable · Windows x64

Quick start: extract the entire ZIP, then run ClashStudio.exe. Keep all folders together.
Language: Settings and logs > Settings > Interface language (Follow system / 简体中文 / English).
The core, Python runtime and four rule databases are bundled. System WebView2 is required.
Startup diagnostics: data/startup.log and data/tauri-backend.log.


1. 将整个ZIP解压到可写文件夹，再双击 ClashStudio.exe。请勿在压缩包内直接运行。
2. 系统需已有 Microsoft Edge WebView2 Runtime；本机已安装。无需安装 Python、Node、Rust 或开发工具。
3. 在软件中选择TUN并启动，可请求管理员权限并连接后台助手，主窗口无需重启；首次迁移内核可能短暂断网。“管理员启动.cmd”作为兼容入口保留。
4. 首次启动是空白配置，自行导入订阅；本包不包含开发者的订阅、密码、日志或代理设置。
5. 订阅、日志、WebView配色及缓存保存在程序旁data目录。移动/备份请关闭程序后复制整个文件夹。
6. 正常退出会停止自己的内核并恢复本程序设置的系统代理；异常中断后可使用“恢复系统代理.cmd”。
7. 同时只运行一个Clash Studio版本。升级前关闭旧版，保留data目录并备份。
8. 未做干净Windows或另一台电脑实机验收；网络、TUN与自定义主题功能继承开发版。
9. 设置页提供独立的配色及背景照片弹窗。局域网齿轮管理可选认证、密码和地址信息；新配置默认无需认证，旧认证保留。地址列表收在子菜单，IPv6齿轮位于开关左侧。
10. 本版代理端口编辑入口位于“本地运行”。“Clash 设置”集中管理局域网、IPv6及DNS覆写；详细参数点击对应齿轮，修改后保存。
11. 内核、Wintun和四项基础规则库已内置，data/runtime也预置全新数据库，无需另行下载；订阅中额外指定的远程规则集仍取决于该订阅。
12. 设置与日志分为标签，照片背景支持拖动裁切、整窗预览与自动配色。选择后保存才生效，清除背景恢复原配色。

包内容：Tauri桌面程序、Python 3.12独立运行时及最小后端依赖、Mihomo、Wintun、四项GeoData、前端资源。
WebView2官方说明：https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
第三方Python包许可保留在 runtime/python/Lib/site-packages/*dist-info 中。
应用对应源码在 source/ClashStudio-source.zip；Mihomo上游 https://github.com/MetaCubeX/mihomo/tree/v1.19.33 。
''', encoding='utf-8-sig')

    source_zip = OUT / 'source/ClashStudio-source.zip'
    source_zip.parent.mkdir()
    with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for folder in ['server', 'vendor/app', 'vendor/examples', 'frontend/src', 'frontend/public', 'src-tauri/src', 'src-tauri/capabilities', 'src-tauri/icons', 'scripts', 'docs', 'tests']:
            for path in sorted((ROOT / folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ['run.py', 'LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md', '六项优化说明.md', '0.5.17发布说明.md', 'dev-env.ps1', 'build-tauri.ps1', 'frontend/index.html', 'frontend/package.json', 'frontend/pnpm-lock.yaml', 'frontend/tsconfig.json', 'frontend/vite.config.ts', 'src-tauri/Cargo.toml', 'src-tauri/Cargo.lock', 'src-tauri/build.rs', 'src-tauri/tauri.conf.json']:
            archive.write(ROOT / name, name)
    manifest = {'version': '0.5.17-portable', 'typecheck': 'passed', 'frontend_build': 'passed', 'rust_build': 'passed', 'portable_launch': 'not tested', 'uac_and_tun': 'not tested', 'files': [{'path': path.relative_to(OUT).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)} for path in sorted(OUT.rglob('*')) if path.is_file()]}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path, (Path(NAME) / path.relative_to(OUT)).as_posix())
    checksum = digest(ZIP)
    ZIP.with_suffix('.zip.sha256').write_text(f'{checksum}  {ZIP.name}\n', encoding='ascii')
    print(json.dumps({'zip': str(ZIP), 'bytes': ZIP.stat().st_size, 'sha256': checksum, 'file_count': len(manifest['files'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
