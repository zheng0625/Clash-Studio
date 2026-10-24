"""GNOME user proxy settings with durable, ownership-aware restoration."""
import json
import os
from pathlib import Path
import shutil
import subprocess


class GnomeProxy:
    KEYS = [('org.gnome.system.proxy', 'mode'),
            ('org.gnome.system.proxy', 'use-same-proxy'),
            ('org.gnome.system.proxy.http', 'enabled'),
            ('org.gnome.system.proxy.http', 'use-authentication'),
            *[(f'org.gnome.system.proxy.{scheme}', key) for scheme in ('http', 'https', 'socks') for key in ('host', 'port')]]

    def __init__(self, directory):
        self.path = Path(directory) / 'system-proxy-backup.json'

    @staticmethod
    def environment():
        env = os.environ.copy()
        runtime = env.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
        if not env.get('DBUS_SESSION_BUS_ADDRESS') and Path(runtime, 'bus').exists():
            env['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + runtime + '/bus'
        return env

    @classmethod
    def command(cls, *args):
        try:
            result = subprocess.run(['gsettings', *args], env=cls.environment(), capture_output=True, text=True, timeout=4)
        except subprocess.TimeoutExpired as error:
            raise OSError('GNOME proxy settings timed out') from error
        if result.returncode:
            raise OSError('GNOME proxy settings unavailable')
        return result.stdout.strip()

    @classmethod
    def available(cls):
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if desktop and not any(name in desktop for name in ('gnome', 'ubuntu', 'unity')):
            return False
        if not shutil.which('gsettings') or not cls.environment().get('DBUS_SESSION_BUS_ADDRESS'):
            return False
        try:
            return cls.command('writable', 'org.gnome.system.proxy', 'mode') == 'true'
        except (OSError, subprocess.TimeoutExpired):
            return False

    def read(self):
        return {schema + '/' + key: self.command('get', schema, key) for schema, key in self.KEYS}

    def write(self, key, value):
        schema, name = key.rsplit('/', 1)
        self.command('set', schema, name, value)
        if self.command('get', schema, name) != value:
            raise OSError('GNOME proxy setting was not confirmed')

    def backup(self):
        if not self.path.exists():
            return None
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if value.get('adapter') != 'gnome':
            raise ValueError('Proxy backup belongs to another platform; preserve it for recovery')
        return value

    def save_backup(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream)
        temporary.replace(self.path)

    def status(self):
        current = self.read()
        backup = self.backup()
        enabled = current['org.gnome.system.proxy/mode'] == "'manual'"
        host = current['org.gnome.system.proxy.http/host'].strip("'")
        port = current['org.gnome.system.proxy.http/port']
        return {'supported': True, 'enabled': enabled, 'server': f'{host}:{port}' if enabled else '',
                'owned': bool(backup and current == backup['applied'])}

    def enable(self, port):
        if not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ValueError('Invalid proxy port')
        if self.path.exists():
            if not self.status()['owned']:
                raise ValueError('GNOME proxy changed externally; backup retained')
            if self.backup()['applied']['org.gnome.system.proxy.http/port'] == str(port):
                return self.status()
            self.restore()
        previous = self.read()
        applied = dict(previous)
        applied['org.gnome.system.proxy/mode'] = "'manual'"
        applied['org.gnome.system.proxy/use-same-proxy'] = 'true'
        applied['org.gnome.system.proxy.http/enabled'] = 'true'
        applied['org.gnome.system.proxy.http/use-authentication'] = 'false'
        for scheme in ('http', 'https', 'socks'):
            applied[f'org.gnome.system.proxy.{scheme}/host'] = "'127.0.0.1'"
            applied[f'org.gnome.system.proxy.{scheme}/port'] = str(port)
        self.save_backup({'adapter': 'gnome', 'values': previous, 'applied': applied})
        changed = []
        try:
            # Switch mode last, after all endpoints have been configured.
            for key in [k for k in applied if k != 'org.gnome.system.proxy/mode'] + ['org.gnome.system.proxy/mode']:
                changed.append(key)
                self.write(key, applied[key])
            return self.status()
        except (OSError, subprocess.TimeoutExpired):
            recovered = True
            for key in reversed(changed):
                try:
                    self.write(key, previous[key])
                except (OSError, subprocess.TimeoutExpired):
                    recovered = False
            if recovered:
                self.path.unlink()
            raise

    def restore(self):
        backup = self.backup()
        if not backup:
            return {'restored': False, 'reason': '没有待恢复的代理设置'}
        current = self.read()
        if current != backup['applied'] and not backup.get('restoring'):
            return {'restored': False, 'reason': '系统代理已被其他程序更改，保留备份且未覆盖'}
        # Also permit retry after a partially completed restoration.
        if any(current[k] not in (backup['applied'][k], backup['values'][k]) for k in current):
            return {'restored': False, 'reason': '系统代理已被其他程序更改，保留备份且未覆盖'}
        backup['restoring'] = True
        self.save_backup(backup)
        self.write('org.gnome.system.proxy/mode', "'none'")
        for key, value in backup['values'].items():
            if key != 'org.gnome.system.proxy/mode':
                self.write(key, value)
        self.write('org.gnome.system.proxy/mode', backup['values']['org.gnome.system.proxy/mode'])
        self.path.unlink()
        return {'restored': True}
