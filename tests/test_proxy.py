import json

from server.proxy import SystemProxy


def test_proxy_backup_restoration_and_external_change_are_ownership_aware(tmp_path, monkeypatch):
    # Exercise the Windows adapter with a fake registry on every build host.
    from types import SimpleNamespace
    import server.proxy as proxy_module
    monkeypatch.setattr(proxy_module, 'sys', SimpleNamespace(platform='win32'))
    values = {"ProxyEnable": (1, 4), "ProxyServer": ("original.example:8080", 1)}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Registry:
        REG_SZ, REG_DWORD = 1, 4

        def QueryValueEx(self, key, name):
            if name not in values:
                raise FileNotFoundError()
            return values[name]

        def SetValueEx(self, key, name, reserved, kind, value):
            values[name] = (value, kind)

        def DeleteValue(self, key, name):
            values.pop(name)

    proxy = SystemProxy(tmp_path)
    monkeypatch.setattr(proxy, "registry", lambda: (Registry(), Key()))
    monkeypatch.setattr(proxy, "notify", lambda: None)
    assert proxy.enable(17890)["owned"]
    assert proxy.path.exists()
    assert proxy.restore()["restored"]
    assert values["ProxyServer"][0] == "original.example:8080"
    assert not proxy.path.exists()
    proxy.enable(17890)
    values["ProxyServer"] = ("another-app:7890", 1)
    assert not proxy.restore()["restored"]
    assert values["ProxyServer"][0] == "another-app:7890"
    assert json.loads(proxy.path.read_text())["values"]["ProxyServer"][0] == "original.example:8080"
