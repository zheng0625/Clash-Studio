"""Resource files are read-only; all mutable state belongs to data_dir."""
from dataclasses import dataclass
from pathlib import Path
import os
import sys


def default_data_dir(resources: Path, *, platform=None, env=None):
    platform, env = platform or sys.platform, os.environ if env is None else env
    if env.get('CLASH_STUDIO_DATA'):
        return Path(env['CLASH_STUDIO_DATA']).expanduser().absolute()
    if platform == 'win32' and (resources / 'installed.json').is_file():
        return Path(env.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'ClashStudio'
    if (resources / 'portable.json').is_file() or platform == 'win32':
        return resources / 'data'
    user = Path(env.get('HOME') or Path.home())
    if platform == 'darwin':
        return user / 'Library/Application Support/ClashStudio'
    return Path(env.get('XDG_DATA_HOME') or user / '.local/share') / 'clash-studio'


@dataclass(frozen=True)
class AppPaths:
    resources: Path
    data: Path

    @classmethod
    def for_app(cls, resources, data_dir=None):
        resources = Path(resources).resolve()
        # Embedded callers/tests retain the historical isolated home/data contract.
        return cls(resources, Path(data_dir).expanduser().resolve() if data_dir is not None else resources / 'data')

    @property
    def runtime(self):
        return self.data / 'runtime'

    @property
    def webview(self):
        return self.data / 'webview2'

    def describe(self):
        return {'resources': str(self.resources), 'data': str(self.data), 'runtime': str(self.runtime)}
