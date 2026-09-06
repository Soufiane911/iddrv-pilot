from dataclasses import replace
import httpx
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import machine_connections as api
from backend.app import config
from test_erp_import_api import headers

BODY = {'base_url': 'http://machine.test', 'external_machine_id': '606', 'secret_ref': 'PRESS', 'poll_interval_s': 1, 'enabled': False, 'mapping_profile': 'iddrv-cycle-v1'}


def setup(monkeypatch):
    monkeypatch.setattr(api, 'local_machine', lambda _: {'id': 606, 'site_id': 1})
    monkeypatch.setattr(config, 'settings', replace(config.settings, telemetry_allowed_origins=('http://machine.test',), telemetry_allow_http=True))
    monkeypatch.setattr(api, 'get_connection_config', lambda _: BODY)
    return TestClient(app)


def test_viewer_can_read_but_not_edit_or_test(monkeypatch):
    client = setup(monkeypatch)
    assert client.get('/api/v1/machines/606/connection', headers=headers('viewer')).status_code == 200
    assert client.put('/api/v1/machines/606/connection', headers=headers('viewer'), json=BODY).status_code == 403
    assert client.post('/api/v1/machines/606/connection/test', headers=headers('viewer'), json=BODY).status_code == 403


def test_machine_site_resolved_on_server_and_secret_reference_only(monkeypatch):
    client = setup(monkeypatch)
    monkeypatch.setenv('TELEMETRY_SECRET_PRESS', 'never-disclose-me')
    response = client.get('/api/v1/machines/606/connection', headers=headers('viewer'))
    assert response.json()['secret_ref'] == 'PRESS'
    assert 'never-disclose-me' not in response.text
    for method in ('get', 'put', 'post'):
        path = '/api/v1/machines/606/connection' + ('/test' if method == 'post' else '')
        kwargs = {'json': BODY} if method != 'get' else {}
        assert getattr(client, method)(path, headers=headers('supervisor', site=2), **kwargs).status_code == 404


def test_test_is_read_only_for_enable_and_returns_oldest_available(monkeypatch):
    client = setup(monkeypatch)
    def http(request):
        if request.url.path.endswith('/status'):
            return httpx.Response(200, json={'schema_version': 1, 'stream_id': 's', 'machine_id': '606', 'machine_state': 'unknown', 'observed_at': '2026-09-05T00:00:00Z', 'oldest_available_at': '2026-09-04T00:00:00Z'})
        return httpx.Response(200, json={'schema_version': 1, 'stream_id': 's', 'items': [], 'next_cursor': None, 'has_more': False})
    monkeypatch.setattr(api, 'configured_client', lambda *a: httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(http)))
    recorded = []
    monkeypatch.setattr(api, 'record_test', lambda *args: recorded.append(args))
    monkeypatch.setattr(api, 'save_connection', lambda *a: (_ for _ in ()).throw(AssertionError('test must not configure')))
    response = client.post('/api/v1/machines/606/connection/test', headers=headers('supervisor'), json=BODY)
    assert response.json()['ok'] is True
    assert response.json()['source_state'] == 'unknown'
    assert response.json()['oldest_available_at'] == '2026-09-04T00:00:00Z'
    assert client.get('/api/v1/machines/606/connection', headers=headers('viewer')).json()['enabled'] is False


def test_unapproved_origin_and_site_input_are_rejected(monkeypatch):
    client = setup(monkeypatch)
    assert client.put('/api/v1/machines/606/connection', headers=headers('supervisor'), json={**BODY, 'base_url': 'http://evil.test'}).status_code == 422
    assert client.put('/api/v1/machines/606/connection', headers=headers('supervisor'), json={**BODY, 'site_id': 2}).status_code == 422


def test_product_api_never_mounts_fixture_controls():
    paths = {route.path for route in app.routes}
    assert '/__test/control' not in paths


def test_continuity_recovery_rejects_stale_confirmation_before_mutation(monkeypatch):
    class Cursor:
        def __init__(self):
            self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, *args, **kwargs): self.calls += 1
        def fetchone(self):
            if self.calls == 1:
                return {'id': 'connection-1', 'state': 'gap_detected', 'base_url': 'http://machine.test', 'secret_ref': 'PRESS', 'external_machine_id': '606'}
            return {'stream_id': 'stream-a', 'cursor': 'stream-a:9', 'last_sequence': 9}

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def cursor(self, **kwargs): return Cursor()

    monkeypatch.setattr('backend.app.db.get_connection', lambda: Connection())
    client = setup(monkeypatch)
    payload = {'decision': 'resume_available', 'expected_stream_id': 'stream-a', 'expected_cursor': 'stream-a:8',
               'new_stream_id': 'stream-a', 'available_from_sequence': 10, 'resume_cursor': 'stream-a:9',
               'confirmation': 'I understand the gap and retained history'}
    response = client.post('/api/v1/machines/606/connection/continuity/recover', headers=headers('supervisor'), json=payload)
    assert response.status_code == 409
    assert response.json()['error']['message'] == 'continuity_confirmation_stale'
