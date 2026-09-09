"""Production error middleware, admission, readiness and disposable smoke guards."""
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_summary6_api import client, headers, body, BASE
from backend.app.services import summary6 as service
from backend.app.services import summary6_admission as admission


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', '1e309', '9' * 400])
@pytest.mark.parametrize('field', ['through_cycle', 'site_id'])
def test_nonfinite_body(client, value, field):
    payload = body()
    if field == 'through_cycle':
        payload['source'][field] = 'REPLACE'
    else:
        payload[field] = 'REPLACE'
    response = client.post(BASE + '/replay', headers=headers(),
                           content=json.dumps(payload).replace('"REPLACE"', value))
    assert response.status_code == 422, response.text
    assert response.json()['error']['code'] == 'validation_error'
    assert response.headers['x-request-id']
    for error in response.json()['error']['details']['errors']:
        assert set(error) == {'type', 'loc', 'msg'}


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', '1e309', '9' * 400])
def test_bad_site_query(client, value):
    response = client.get(BASE + '/demo-datasets', params={'site_id': value}, headers=headers())
    assert response.status_code == 422, response.text


@pytest.mark.parametrize('mode', [None, '', 'unknown'])
def test_default_disabled_before_io(client, monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv('HDT_RUNTIME_MODE', raising=False)
    else:
        monkeypatch.setenv('HDT_RUNTIME_MODE', mode)
    loader = Mock(side_effect=AssertionError('no package IO'))
    monkeypatch.setattr(service, 'package', loader)
    assert client.post(BASE+'/replay', json=body(), headers=headers()).status_code == 409
    loader.assert_not_called()
    from ml.runtime_mode import runtime_mode
    assert runtime_mode() == 'disabled'


@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_all_files_checked_readiness_replay_launch(client, monkeypatch, tmp_path, damage):
    shutil.copytree(service.DATA, tmp_path / 'data')
    monkeypatch.setattr(service, 'DATA', tmp_path / 'data')
    monkeypatch.setattr(service, 'package', lambda: SimpleNamespace(runtime_id=service.PACKAGE_ID))
    assert client.get(BASE+'/current', headers=headers()).json()['readiness'] == 'ready'
    # Damage a lot OTHER than the replay target, after a successful readiness call.
    path = service.DATA / 'M3-R2-L15.jsonl.gz'
    path.unlink() if damage == 'missing' else path.write_bytes(b'corrupt')
    state = client.get(BASE+'/current', headers=headers()).json()
    assert state['readiness'] == 'not_ready'
    assert state['reasons'] == ['summary6_dataset_unavailable']
    assert client.post(BASE+'/replay', json=body(), headers=headers()).status_code == 503
    from scripts import smoke_summary6_local as smoke
    docker = Mock(side_effect=AssertionError('no subprocess before preflight'))
    monkeypatch.setattr(smoke.subprocess, 'run', docker)
    with pytest.raises(RuntimeError, match='summary6_preflight_unavailable'):
        smoke.run()
    docker.assert_not_called()


def test_concurrent_replay_identity_and_global_quota(client, monkeypatch):
    from backend.app.security import Identity, create_session_token
    entered, release = Event(), Event()
    loader = Mock(return_value=SimpleNamespace(runtime_id=service.PACKAGE_ID))
    monkeypatch.setattr(service, 'package', loader)
    def slow(*args):
        entered.set()
        assert release.wait(5)
        raise service.Unavailable('summary6_replay_unavailable')
    monkeypatch.setattr(service, 'replay', slow)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, BASE+'/replay', json=body(), headers=headers())
        assert entered.wait(5)
        try:
            # New session token and payload site cannot evade the authenticated user quota.
            for path in ['/replay', '/current']:
                r = (client.post(BASE+path, json=body(), headers=headers()) if path == '/replay'
                     else client.get(BASE+path, headers=headers()))
                assert r.status_code == 429 and r.headers['Retry-After'] == '1'
            with admission.admit(SimpleNamespace(user_id='other')):
                token, _ = create_session_token(Identity('third', 'third@test', 'Third', 'viewer', (7,)))
                r = client.get(BASE+'/current', headers={'Authorization': 'Bearer '+token})
                assert r.status_code == 429
            assert loader.call_count == 1  # all rejection paths precede model loading
        finally:
            release.set()
        assert pending.result().status_code == 503
    assert admission._active == {}
    for i in range(1000):
        with admission.admit(SimpleNamespace(user_id=str(i))):
            assert len(admission._active) == 1
    assert admission._active == {}
    assert client.get(BASE+'/current', headers=headers()).status_code == 200


def test_launch_rejects_missing_package_before_uvicorn(tmp_path):
    import os
    env = dict(os.environ, SUMMARY6_PACKAGE_DIR=str(tmp_path / 'absent'),
               SUMMARY6_MANIFEST_SHA256='0' * 64)
    result = subprocess.run(['bash', 'scripts/launch_summary6_replay.sh'], env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert 'Summary6 unavailable: summary6_package_unavailable' in result.stderr
    assert str(tmp_path) not in result.stderr


def test_smoke_kill_and_owned_cleanup(monkeypatch):
    from scripts import smoke_summary6_local as smoke
    server = Mock()
    server.wait.side_effect = [subprocess.TimeoutExpired('uvicorn', 10), None]
    smoke.stop_server(server)
    server.terminate.assert_called_once()
    server.kill.assert_called_once()
    assert server.wait.call_count == 2
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps([
        {'Id': 'owned-id', 'Config': {'Labels': {'iddrv.summary6.smoke': 'uuid'}}} ])))
    monkeypatch.setattr(smoke.subprocess, 'run', run)
    smoke.remove_owned_container('unique-name', 'uuid')
    assert run.call_args.args[0] == ['docker', 'rm', '-f', 'owned-id']
    run.reset_mock()
    with pytest.raises(RuntimeError, match='ownership_mismatch'):
        smoke.remove_owned_container('unique-name', 'different-uuid')
    assert run.call_count == 1


def test_smoke_finally_removes_even_when_server_cleanup_raises(monkeypatch):
    from scripts import smoke_summary6_local as smoke
    monkeypatch.setattr(service, 'current', lambda: {'replay_enabled': True})
    monkeypatch.setattr(smoke.subprocess, 'run', Mock())
    monkeypatch.setattr(smoke.subprocess, 'check_output', Mock(side_effect=RuntimeError('port failure')))
    monkeypatch.setattr(smoke, 'stop_server', Mock(side_effect=RuntimeError('wait failure')))
    remove = Mock()
    monkeypatch.setattr(smoke, 'remove_owned_container', remove)
    with pytest.raises(RuntimeError, match='wait failure'):
        smoke.run()
    remove.assert_called_once()
    name, owner = remove.call_args.args
    assert name == 'iddrv-summary6-smoke-' + owner and len(owner) == 32
