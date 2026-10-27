"""Package allowlisted corresponding sources without local data or toolchains."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.2'
OUTPUT = ROOT / 'artifacts/releases' / f'ClashStudio-{VERSION}-source.zip'
DIRECTORIES = [
    'server', 'vendor/app', 'vendor/examples', 'frontend/src', 'frontend/public',
    'src-tauri/src', 'src-tauri/capabilities', 'src-tauri/icons', 'scripts', 'tests',
    'docs', 'licenses', 'launcher', 'android/app/src', 'android/gradle',
    'android/vpn-probe/src', 'android/lifecycle-probe/src',
]
FILES = [
    'run.py', 'requirements.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md',
    'README.en.md', 'BUILDING.md', 'RELEASE.md', '1.2发布说明.md', 'dev-env.ps1',
    'build-tauri.ps1', 'frontend/package.json', 'frontend/pnpm-lock.yaml',
    'frontend/index.html', 'frontend/ui-preview.html', 'frontend/ui-editor.html',
    'frontend/ui-android.html', 'frontend/tsconfig.json', 'frontend/vite.config.ts',
    'src-tauri/Cargo.toml', 'src-tauri/Cargo.lock', 'src-tauri/build.rs',
    'src-tauri/tauri.conf.json', 'android/build.gradle.kts', 'android/settings.gradle.kts',
    'android/gradle.properties', 'android/gradlew', 'android/gradlew.bat',
    'android/app/build.gradle.kts', 'android/vpn-probe/build.gradle.kts',
    'android/lifecycle-probe/build.gradle.kts', 'android/README.md',
    'bin/source.json', 'bin/linux-core-source.json', 'bin/geodata/source.json',
]


def main():
    if OUTPUT.exists():
        raise SystemExit('Keep the existing source release; choose a new version.')
    paths = {ROOT / name for name in FILES if (ROOT / name).is_file()}
    for folder in DIRECTORIES:
        paths.update(p for p in (ROOT / folder).rglob('*') if p.is_file())
    entries = []
    with zipfile.ZipFile(OUTPUT, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(paths):
            relative = path.relative_to(ROOT)
            if any(part in {'__pycache__', '.git', 'node_modules', '.gradle', 'build', 'target', 'data', 'artifacts'} for part in relative.parts):
                continue
            if path.suffix in {'.pyc', '.jks', '.keystore', '.p12', '.key', '.exe', '.dll', '.aar'} or path.name.startswith('.env') or path.name == 'local.properties':
                continue
            data = path.read_bytes()
            archive.writestr('ClashStudio-1.2/' + relative.as_posix(), data)
            entries.append({'path': relative.as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        archive.writestr('ClashStudio-1.2/SOURCE-MANIFEST.json', json.dumps({'version': '1.2.0', 'files': entries}, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise SystemExit('Source archive integrity check failed')
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix('.zip.sha256').write_text(f'{digest}  {OUTPUT.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(OUTPUT), 'source_files': len(entries), 'bytes': OUTPUT.stat().st_size, 'sha256': digest}, ensure_ascii=False))


if __name__ == '__main__':
    main()
