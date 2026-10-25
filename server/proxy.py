"""Explicit opt-in WinINET proxy, with recoverable ownership-aware backup."""
import ctypes
import json
import sys
from pathlib import Path


class SystemProxy:
    def __init__(self, directory: Path):
        self.path = directory / "system-proxy-backup.json"

    @staticmethod
    def registry():
        import winreg
        return winreg, winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE)

    def status(self):
        if sys.platform != "win32":
            return {"supported": False, "owned": False, "enabled": False, "server": ""}
        winreg, key = self.registry()
        with key:
            def read(name):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return None
            enabled, server = read("ProxyEnable"), read("ProxyServer")
        backup = json.loads(self.path.read_text()) if self.path.exists() else None
        return {"supported": True, "enabled": bool(enabled), "server": server or "",
                "owned": bool(backup and enabled == 1 and server == backup["applied"])}

    @staticmethod
    def notify():
        for code in (39, 37):
            ctypes.windll.Wininet.InternetSetOptionW(0, code, 0, 0)

    def enable(self, port):
        if sys.platform != "win32":
            raise ValueError("此系统代理实现仅支持 Windows")
        applied = f"127.0.0.1:{port}"
        if self.path.exists():
            if self.status()["owned"]:
                if json.loads(self.path.read_text())["applied"] == applied:
                    return self.status()
                self.restore()
            else:
                raise ValueError("检测到上次备份与当前代理不一致，请先处理恢复提示")
        winreg, key = self.registry()
        with key:
            values = {}
            for name in ("ProxyEnable", "ProxyServer"):
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                    values[name] = [value, kind]
                except FileNotFoundError:
                    values[name] = None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"values": values, "applied": applied}), encoding="utf-8")
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, applied)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        self.notify()
        return self.status()

    def restore(self):
        if not self.path.exists():
            return {"restored": False, "reason": "没有待恢复的代理设置"}
        if not self.status()["owned"]:
            return {"restored": False, "reason": "系统代理已被其他程序更改，未覆盖；保留备份供手动检查"}
        backup = json.loads(self.path.read_text())
        winreg, key = self.registry()
        with key:
            for name, previous in backup["values"].items():
                if previous is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, previous[1], previous[0])
        self.notify()
        self.path.unlink()
        return {"restored": True}
