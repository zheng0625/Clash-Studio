from __future__ import annotations
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029'
MANIFEST = ROOT / 'artifacts' / 'memory' / 'checkpoint-20261029' / 'SHA256SUMS.txt'

entries = []
for line in MANIFEST.read_text(encoding='utf-8').splitlines():
    if '|' not in line:
        continue
    rel, digest, size = line.split('|')
    rel = rel.replace('\\', '/')
    entries.append((rel, digest, int(size)))

missing = []
mismatch = []
for rel, digest, size in entries:
    target = OUT / rel
    if not target.exists():
        source = ROOT / rel
        if not source.exists():
            missing.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    data = target.read_bytes()
    actual = hashlib.sha256(data).hexdigest().upper()
    if actual != digest or len(data) != size:
        mismatch.append((rel, actual, digest, len(data), size))

print(f'entries={len(entries)} missing={len(missing)} mismatch={len(mismatch)}')
for item in mismatch:
    print('MISMATCH', item)
for rel in missing:
    print('MISSING', rel)

verified = OUT / 'MANIFEST-verified.txt'
with verified.open('w', encoding='utf-8', newline='\n') as handle:
    for rel, digest, size in entries:
        handle.write(f'{rel}|{digest}|{size}\n')

archive = ROOT / 'artifacts' / 'memory' / 'baseline-source-20261029.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path != verified:
            bundle.write(path, path.relative_to(OUT))
print('archive', archive, archive.stat().st_size)
