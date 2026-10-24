import pytest
from server.gnome_proxy import GnomeProxy


def fake(tmp_path, monkeypatch):
    proxy = GnomeProxy(tmp_path)
    values = {schema+'/'+key: "'none'" if key=='mode' else "'previous'" if key=='host' else 'true' if key in ('use-same-proxy','use-authentication') else 'false' if key=='enabled' else '8080' for schema,key in proxy.KEYS}
    previous=dict(values)
    monkeypatch.setattr(proxy,'read',lambda:dict(values))
    monkeypatch.setattr(proxy,'write',lambda key,value:values.__setitem__(key,value))
    return proxy,values,previous


def test_gnome_proxy_enable_restore_and_external_change(tmp_path,monkeypatch):
    proxy,values,previous=fake(tmp_path,monkeypatch)
    assert proxy.enable(17890)['owned']
    assert values['org.gnome.system.proxy/mode']=="'manual'"
    for scheme in ('http','https','socks'):
        assert values[f'org.gnome.system.proxy.{scheme}/port']=='17890'
    assert proxy.restore()['restored'] and values==previous
    proxy.enable(17890)
    values['org.gnome.system.proxy/mode']="'none'"
    assert not proxy.restore()['restored'] and proxy.path.exists()


def test_gnome_partial_apply_rolls_back(tmp_path,monkeypatch):
    proxy,values,previous=fake(tmp_path,monkeypatch)
    failed=[False]
    def write(key,value):
        if key=='org.gnome.system.proxy.https/port' and not failed[0]:
            failed[0]=True
            raise OSError('test write failure')
        values[key]=value
    monkeypatch.setattr(proxy,'write',write)
    with pytest.raises(OSError):proxy.enable(17890)
    assert values==previous and not proxy.path.exists()


def test_gnome_restore_retry_after_failure(tmp_path,monkeypatch):
    proxy,values,previous=fake(tmp_path,monkeypatch)
    proxy.enable(17890)
    def fail(key,value):
        if key=='org.gnome.system.proxy.https/port':raise OSError('interrupted restore')
        values[key]=value
    monkeypatch.setattr(proxy,'write',fail)
    with pytest.raises(OSError):proxy.restore()
    assert proxy.path.exists()
    monkeypatch.setattr(proxy,'write',lambda key,value:values.__setitem__(key,value))
    assert proxy.restore()['restored'] and values==previous
