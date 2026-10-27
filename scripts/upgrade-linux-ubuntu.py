"""One-off, narrowly scoped 0.5.12 -> 0.5.13 Ubuntu portable upgrade."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

home=Path('/home/zheng')
old=home/'Applications/ClashStudio-0.5.12-linux-x64-preview1'
new=home/'Applications/ClashStudio-0.5.13-linux-x64-preview1'
backup=home/'.clashstudio-debug/backups/0.5.12-before-0.5.13'
assert old.resolve()==old and new.resolve()==new
assert subprocess.run(['pgrep','-x','ClashStudio'],capture_output=True).returncode==1, 'Stop desktop before upgrading'
for entry in json.loads((new/'manifest.json').read_text())['files']:
    path=(new/entry['path']).resolve()
    assert path.is_relative_to(new)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'], entry['path']
if sys.argv[1]=='prepare':
    assert (old/'data/studio.sqlite3').is_file()
    assert not backup.exists() and not (new/'data').exists()
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(old/'data',backup)
    shutil.copytree(backup,new/'data')
    for path in (backup).rglob('*'):
        if path.is_file():
            relative=path.relative_to(backup)
            assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256((new/'data'/relative).read_bytes()).digest()
    print(json.dumps({'backup':str(backup),'user_data_copied_and_verified':True}))
elif sys.argv[1]=='remove-old':
    assert (backup/'studio.sqlite3').is_file() and (new/'data/studio.sqlite3').is_file()
    # Exact resolved old version only; never delete a workspace or user-data backup.
    shutil.rmtree(old)
    for name in ['ClashStudio-0.5.12-linux-x64-preview1.tar.gz','ClashStudio-0.5.12-linux-x64-preview1.tar.gz.sha256']:
        (home/name).unlink(missing_ok=True)
    print(json.dumps({'old_program_and_archive_removed':True,'user_data_backup_retained':True}))
else:raise SystemExit('Expected prepare or remove-old')
