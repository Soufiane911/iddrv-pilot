from copy import deepcopy
import pytest
from ingest.telemetry.http_source import validate_page, SourceError


def payload(n=1):
    return {'schema_version': 1, 'stream_id': 'stream-A', 'items': [{'event_id': f'stream-A:{i}', 'sequence': i, 'machine_id': '606', 'cycle_counter': i, 'cycle_ended_at': '2026-09-05T08:00:12+02:00', 'measurements': {'cycle_time_s': 12.0, 'unmapped_sensor': 3.2}} for i in range(1, n+1)], 'next_cursor': f'cursor-{n}', 'has_more': False}


def validate(value):
    return validate_page(value, expected_machine_id='606', expected_stream_id='stream-A')


def test_invalid_identifiable_row_kept_next_to_valid_row():
    p = payload(2)
    p['items'][0]['cycle_ended_at'] = '2026-09-05T08:00:12'
    page = validate(p)
    assert page.items[0].rejection_reason == 'cycle_timezone_required'
    assert page.items[1].rejection_reason is None
    assert page.items[1].raw['measurements']['unmapped_sensor'] == 3.2


@pytest.mark.parametrize('change', [lambda p: p.update(stream_id='other'), lambda p: p.update(schema_version=2), lambda p: p.update(next_cursor=None, has_more=True), lambda p: p['items'][0].update(machine_id='other'), lambda p: p['items'][0].pop('event_id'), lambda p: p['items'].reverse()])
def test_envelope_and_identity_errors_block_page(change):
    p = payload(2)
    change(p)
    with pytest.raises(SourceError):
        validate(p)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), '12 seconds', True, 1e99])
def test_invalid_measurements_are_explicit_rejections(value):
    p = payload()
    p['items'][0]['measurements']['cycle_time_s'] = value
    assert validate(p).items[0].rejection_reason


def test_reset_hardware_counter_and_late_event_are_valid():
    p = payload(2)
    p['items'][1].update(cycle_counter=0, cycle_ended_at='2026-09-04T08:00:12+02:00')
    assert all(i.rejection_reason is None for i in validate(p).items)


def test_external_fixture_private_control_and_persistent_stream(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from tests.fixtures.press_api import app as fixture
    monkeypatch.setattr(fixture, 'DB_PATH', str(tmp_path/'fixture.sqlite'))
    monkeypatch.setenv('PRESS_FIXTURE_CONTROL_TOKEN', 'synthetic-control')
    client = TestClient(fixture.app)
    assert client.post('/__test/control', json={'emit': 2}).status_code == 404
    assert client.post('/__test/control', headers={'X-Test-Control-Token': 'synthetic-control'}, json={'emit': 2}).status_code == 200
    first = client.get('/v1/machines/606/cycles?limit=1').json()
    assert first['has_more'] is True
    # Fresh HTTP client / DB connection sees the same stable stream and cursor.
    second = TestClient(fixture.app).get('/v1/machines/606/cycles', params={'after': first['next_cursor']}).json()
    assert second['stream_id'] == first['stream_id']
    assert second['items'][0]['sequence'] == 2


@pytest.mark.parametrize('measurement', [10**400, -(10**400)])
def test_huge_integer_measurement_rejects_only_its_event(measurement):
    p = payload(2)
    p['items'][0]['measurements']['cycle_time_s'] = measurement
    page = validate(p)
    assert page.items[0].rejection_reason == 'measurement_invalid'
    assert page.items[1].rejection_reason is None
    assert page.next_cursor == 'cursor-2'


@pytest.mark.parametrize('key,value,valid', [
    ('cycle_time_s', 9999.995, True),
    ('cycle_time_s', 9999.9994, True),
    ('cycle_time_s', 9999.9995, False),
    ('cushion_mm', 999.9994, True),
    ('cushion_mm', 999.9995, False),
    ('peak_pressure_bar', 999999.994, True),
    ('peak_pressure_bar', 999999.995, False),
    ('barrel_temp_zone1_c', -9999.994, True),
    ('barrel_temp_zone1_c', -9999.995, False),
    ('energy_kwh', 999999.99994, True),
    ('energy_kwh', 999999.99995, False),
])
def test_numeric_limits_follow_sql_column_scale(key, value, valid):
    p = payload()
    p['items'][0]['measurements'][key] = value
    assert (validate(p).items[0].rejection_reason is None) is valid


def test_private_source_complete_profile_and_partial_are_distinct(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from tests.fixtures.press_api import app as fixture
    from ml.process_drift import DRIFT_NUMERIC_FEATURES
    monkeypatch.setattr(fixture,'DB_PATH',str(tmp_path/'press.sqlite'))
    monkeypatch.setenv('PRESS_FIXTURE_CONTROL_TOKEN','synthetic-private-control')
    client=TestClient(fixture.app)
    assert client.post('/__test/control',json={'emit':1}).status_code==404
    headers={'X-Test-Control-Token':'synthetic-private-control'}
    response=client.post('/__test/control',headers=headers,json={'emit':2,'profile':'complete','start_at':'2026-09-05T12:59:48+02:00'})
    assert response.status_code==200
    page=client.get('/v1/machines/606/cycles').json()
    assert page['items'][1]['cycle_ended_at']=='2026-09-05T13:00:00+02:00'
    assert set(DRIFT_NUMERIC_FEATURES)<=set(page['items'][0]['measurements'])
    client.post('/__test/control',headers=headers,json={'emit':1,'profile':'partial'})
    latest=client.get('/v1/machines/606/cycles').json()['items'][-1]
    assert set(latest['measurements'])=={'cycle_time_s','injection_time_s'}
