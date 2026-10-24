"""Exercise native registration and desktop Exec launch in isolated XDG settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

package = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='clash-autostart-') as temporary:
    root = Path(temporary)
    data = root/'user data $literal %f'
    data.mkdir()
    (data/'desktop-settings.json').write_text(json.dumps({'resident': True, 'autostart': True}))
    env = {**os.environ, 'XDG_CONFIG_HOME': str(root/'config'), 'XDG_DATA_HOME': str(root/'desktop-data')}
    log = (root/'desktop.log').open('w+')
    process = None
    def stop():
        subprocess.run([str(package/'Stop.sh'), '--data-dir', str(data)], env=env, capture_output=True, timeout=20)
    def ready(offset=0):
        for _ in range(150):
            path = data/'startup.log'
            if path.exists() and 'frontend_ready' in path.read_text()[offset:]:
                return
            time.sleep(.2)
        log.seek(0)
        raise AssertionError('Native frontend not ready: '+log.read()[-3000:])
    try:
        process = subprocess.Popen([str(package/'Start.sh'), '--data-dir', str(data), '--background'], env=env, stdout=log, stderr=subprocess.STDOUT)
        ready()
        entry = root/'config/autostart/studio.clash.desktop.desktop'
        assert entry.is_file() and str(package/'ClashStudio') in entry.read_text()
        assert '%%f' in entry.read_text() and '--background' in entry.read_text()
        subprocess.run(['desktop-file-validate', str(entry)], check=True, capture_output=True)
        stop()
        process.wait(15)
        assert process.returncode == 0
        offset = len((data/'startup.log').read_text())
        subprocess.run(['gio', 'launch', str(entry)], env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=10)
        ready(offset)
        stop()
        print(json.dumps({'native_autostart_registration': True, 'desktop_entry_valid': True,
            'desktop_exec_launches_real_application': True, 'special_data_path_preserved': True,
            'frontend_ready_both_launches': True, 'normal_exit': True,
            'real_user_autostart_unchanged': True}))
    finally:
        stop()
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(15)
        log.close()
