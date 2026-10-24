"""Linux TUN authorization: only the bundled core receives network capabilities."""
import os
from pathlib import Path
import struct
import subprocess
import threading
import json

from fastapi import HTTPException


class LinuxElevation:
    def __init__(self, home, data_dir=None):
        from .platforms import core_binary
        self.binary = core_binary(Path(home)).resolve()
        self.data_dir = Path(data_dir) if data_dir is not None else Path(home) / 'data'
        self.lock = threading.RLock()

    @property
    def ready(self):
        if os.geteuid() == 0:
            return True
        try:
            value = os.getxattr(self.binary, 'security.capability')
            # v2/v3 file capabilities: effective flag and permitted low word.
            if len(value) not in (20, 24):
                return False
            flags, permitted = struct.unpack_from('<II', value)
            required = (1 << 10) | (1 << 12) | (1 << 13)
            return bool(flags & 1) and permitted & required == required
        except OSError:
            return False

    def ensure(self):
        with self.lock:
            if not Path('/dev/net/tun').is_char_device():
                raise HTTPException(503, 'Linux 缺少 /dev/net/tun，请先启用系统 TUN 设备')
            if not self.binary.is_file():
                raise HTTPException(503, '缺少随附的 Mihomo 内核')
            if self.ready:
                return
            pkexec = Path('/usr/bin/pkexec')
            setcap = next((p for p in (Path('/usr/sbin/setcap'), Path('/sbin/setcap')) if p.is_file()), None)
            if not pkexec.is_file() or setcap is None:
                raise HTTPException(503, 'Linux TUN 授权需要 polkit 和 libcap2-bin，请先安装系统依赖')
            try:
                try:
                    language = json.loads((self.data_dir/'desktop-language.json').read_text())
                except (OSError, ValueError):
                    language = 'auto'
                if language not in ('zh-CN', 'en'):
                    language = 'zh-CN' if os.environ.get('LANG', '').lower().startswith('zh') else 'en'
                result = subprocess.run(['/usr/bin/python3', '-I', '-B', str(Path(__file__).with_name('linux_auth_agent.py')),
                    str(self.binary), language], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, text=True, timeout=90)
            except subprocess.TimeoutExpired:
                raise HTTPException(504, 'Linux TUN 授权超时，原模式保持不变') from None
            except OSError:
                raise HTTPException(503, 'Linux TUN 系统授权程序无法启动') from None
            if result.returncode == 69:
                raise HTTPException(503, 'Linux 图形认证代理不可用，请安装 python3-gi、gir1.2-polkit-1.0 和 gir1.2-gtk-3.0，并在图形桌面重试')
            if result.returncode or not self.ready:
                raise HTTPException(409, 'Linux TUN 授权已取消或未生效，原模式保持不变；请检查桌面认证代理和文件系统能力支持')

    def close(self):
        # File capabilities belong to this executable and survive app exit.
        pass
