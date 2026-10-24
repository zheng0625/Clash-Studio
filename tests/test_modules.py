import pytest
from fastapi import HTTPException

from server.modules import Module, Plan, Workspace, WorkspaceStore, compose

CONFIG = """
proxies:
  - {name: Proxy, type: ss, server: 127.0.0.1, port: 1, cipher: aes-128-gcm, password: test-only}
proxy-groups:
  - {name: Locked, type: select, proxies: [Proxy]}
  - {name: Open, type: select, proxies: [Locked, DIRECT]}
  - {name: Dynamic, type: select, include-all-proxies: true}
rules: [MATCH,DIRECT]
""".replace("rules: [MATCH,DIRECT]", 'rules: ["MATCH,DIRECT"]')


def state(target="Locked", strict=True):
    module = Module(id="work", name="工作", target=target, strict=strict,
                    matches=[{"kind": "DOMAIN-SUFFIX", "value": "example.org"}])
    return Workspace(modules=[module], plans={"profile": Plan(module_ids=["work"])})


def test_source_untouched_overlay_order_and_nested_strict():
    result = compose(CONFIG, "profile", state())
    assert result["errors"] == []
    assert result["config"]["rules"] == ["DOMAIN-SUFFIX,example.org,Locked", "MATCH,DIRECT"]
    assert "DOMAIN-SUFFIX" not in CONFIG
    assert any("DIRECT" in e for e in compose(CONFIG, "profile", state("Open"))["errors"])
    assert compose(CONFIG, "profile", state("Dynamic"))["errors"]
    assert not compose(CONFIG, "profile", state("DIRECT", strict=False))["errors"]


def test_strict_checks_alias_direct_and_dialer_chain():
    direct = CONFIG.replace("type: ss, server: 127.0.0.1, port: 1, cipher: aes-128-gcm, password: test-only", "type: direct")
    assert compose(direct, "profile", state())["errors"]
    via = CONFIG.replace("password: test-only", "password: test-only, dialer-proxy: Open")
    assert compose(via, "profile", state())["errors"]


def test_default_replacement_and_invalid_network():
    workspace = state()
    workspace.plans["profile"].default_target = "REJECT"
    workspace.modules[0].matches[0].kind = "IP-CIDR"
    workspace.modules[0].matches[0].value = "not-a-network"
    result = compose(CONFIG, "profile", workspace)
    assert result["errors"]
    assert result["config"]["rules"][-1] == "MATCH,REJECT"


def test_optimistic_revision_and_reference_validation(tmp_path):
    store = WorkspaceStore(tmp_path / "workspace.json")
    saved = store.save(state())
    assert saved.revision == 2
    assert store.load().plans["profile"].module_ids == ["work"]
    with pytest.raises(HTTPException) as error:
        store.save(state())
    assert error.value.status_code == 409
    saved.plans["profile"].module_ids.append("missing")
    with pytest.raises(HTTPException) as error:
        store.save(saved)
    assert error.value.status_code == 422
