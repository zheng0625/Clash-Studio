import json
from pathlib import Path

import pytest
from app.engine import parse_config
from server.contracts import envelope


def test_common_android_desktop_contract(tmp_path):
    fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('backend-contract.json').read_text(encoding='utf-8'))
    for row in fixture['valid']:
        config = parse_config(row['yaml'])
        assert len(config['proxies']) == row['nodes']
        assert len(config['proxy-groups']) == row['groups']
        assert config['rules'] == row['rules']
    for yaml in fixture['invalid']:
        with pytest.raises(Exception):
            parse_config(yaml)
    for row in fixture['errors']:
        error = envelope(row['status'], 'test', 'test-id')['error']
        assert error['code'] == row['code']
        assert error['retryable'] == row['retryable']
        assert error['operation_id'] == 'test-id'


    from fastapi import HTTPException
    from server.modules import Workspace, WorkspaceStore
    store = WorkspaceStore(tmp_path/'workspace.json')
    stale = fixture['stale_revision']
    saved = store.save(Workspace(revision=stale['request']))
    assert saved.revision == stale['saved']
    with pytest.raises(HTTPException) as error:
        store.save(Workspace(revision=stale['request']))
    assert error.value.status_code == stale['status']
