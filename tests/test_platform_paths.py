from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from server.api import build_app
from server.paths import default_data_dir
from server.platforms import core_binary, platform_info


@pytest.mark.parametrize('system,machine,name', [('win32','AMD64','mihomo-windows-amd64-compatible.exe'),('linux','x86_64','mihomo-linux-amd64'),('linux','aarch64','mihomo-linux-arm64'),('darwin','arm64','mihomo-darwin-arm64'),('darwin','x86_64','mihomo-darwin-amd64')])
def test_core_targets(system,machine,name):
    info=platform_info(system,machine)
    assert core_binary(Path('/resources'),info).name == name
    assert info['capabilities']['system_proxy'] == (system=='win32')


def test_directory_contract(tmp_path):
    resources=tmp_path/'resources'
    user=tmp_path/'user'
    assert default_data_dir(resources,platform='win32',env={}) == resources/'data'
    assert default_data_dir(resources,platform='darwin',env={'HOME':str(user)}) == user/'Library/Application Support/ClashStudio'
    assert default_data_dir(resources,platform='linux',env={'HOME':str(user)}) == user/'.local/share/clash-studio'
    assert default_data_dir(resources,platform='linux',env={'XDG_DATA_HOME':str(user)}) == user/'clash-studio'
    resources.mkdir();(resources/'portable.json').touch()
    assert default_data_dir(resources,platform='linux',env={}) == resources/'data'
    assert default_data_dir(resources,platform='linux',env={'CLASH_STUDIO_DATA':str(user)}) == user


def test_external_data_isolation_and_persistence(tmp_path):
    resources=tmp_path/'read-only-resources';resources.mkdir()
    data=tmp_path/'用户数据'
    app=build_app(resources,data_dir=data)
    headers={'X-Clash-Studio':'1'}
    with TestClient(app) as client:
        profile=client.post('/api/subscriptions',headers=headers,json={'title':'external-data','source_type':'file','yaml':'proxies: []\nproxy-groups: []\nrules: ["MATCH,DIRECT"]\n'})
        assert profile.status_code==201,profile.text
        assert client.put('/api/client/tray/context',headers=headers,json={'profile_id':profile.json()['id']}).status_code==200
        assert client.put('/api/client/runtime/routing-mode',headers=headers,json={'mode':'direct'}).status_code==200
        contract=client.get('/api/client/platform').json()
        assert contract['schema_version']==1 and contract['paths']['data']==str(data.resolve())
        assert app.state.runtime.elevation.data_dir==data.resolve()
        app.state.runtime.platform.info=platform_info('linux','x86_64')
        with pytest.raises(HTTPException) as failure:
            app.state.runtime.change_mode('tun')
        assert failure.value.status_code==409  # Linux supports TUN; a running core is still required.
    assert not (resources/'data').exists()
    assert (data/'tray-context.json').is_file() and (data/'routing-mode.json').is_file()
    with TestClient(build_app(resources,data_dir=data)) as client:
        assert client.get('/api/subscriptions').json()[0]['title']=='external-data'
        assert client.get('/api/client/tray').json()['routing_mode']=='direct'
