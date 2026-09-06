import httpx
import pytest
from ingest.telemetry.http_source import ApiCycleSource, SourceError, validate_origin


def test_reads_since_persisted_cursor():
    def handler(request):
        assert request.url.path == '/v1/machines/606/cycles'
        assert request.url.params['after'] == 'cursor-1528'
        return httpx.Response(200, json={'schema_version': 1, 'stream_id': 'stream-A', 'items': [{'event_id': 'stream-A:1529', 'sequence': 1529, 'machine_id': '606', 'cycle_counter': 1529, 'cycle_ended_at': '2026-09-05T08:00:12+02:00', 'measurements': {'cycle_time_s': 12.0}}], 'next_cursor': 'cursor-1529', 'has_more': False})
    with httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(handler)) as client:
        page = ApiCycleSource(client).fetch_page('606', after='cursor-1528')
    assert page.items[0].sequence == 1529
    assert page.next_cursor == 'cursor-1529'


@pytest.mark.parametrize('status,state,retryable', [(401, 'access_error', False), (403, 'access_error', False), (404, 'configuration_error', False), (410, 'gap_detected', False), (429, 'retrying', True), (503, 'retrying', True), (302, 'contract_error', False)])
def test_http_errors_are_public_and_categorized(status, state, retryable):
    with httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(lambda r: httpx.Response(status, headers={'Retry-After': '9999'}, text='private token'))) as client:
        with pytest.raises(SourceError) as result:
            ApiCycleSource(client).fetch_page('606', after=None)
    assert result.value.state == state
    assert result.value.retryable == retryable
    assert 'private' not in str(result.value)
    if status == 429:
        assert result.value.retry_after == 30


def test_origin_requires_explicit_http_and_exact_origin():
    assert validate_origin('http://machine.test', ('http://machine.test',), True) == 'http://machine.test'
    for url, allow in [('http://machine.test', False), ('http://machine.test.evil', True), ('http://user:password@machine.test', True), ('http://machine.test/path', True)]:
        with pytest.raises(SourceError):
            validate_origin(url, ('http://machine.test',), allow)


def test_does_not_follow_redirect_even_if_injected_client_follows():
    calls = []
    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={'Location': 'https://other.test'})
    with httpx.Client(base_url='http://machine.test', follow_redirects=True, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(SourceError):
            ApiCycleSource(client).fetch_page('606', after=None)
    assert len(calls) == 1


def test_response_size_and_timeout():
    with httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b' ' * (2 * 1024 * 1024 + 1)))) as client:
        with pytest.raises(SourceError, match='response_too_large'):
            ApiCycleSource(client).fetch_page('606', after=None)
    def timeout(request):
        raise httpx.ReadTimeout('private url')
    with httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(SourceError, match='source_timeout'):
            ApiCycleSource(client).fetch_page('606', after=None)


@pytest.mark.parametrize('payload,after', [({'schema_version': 1, 'stream_id': 's', 'items': [], 'has_more': False, 'next_cursor': 'old'}, 'current'), ({'schema_version': 1, 'stream_id': 's', 'items': [], 'has_more': True, 'next_cursor': 'current'}, 'current')])
def test_empty_page_cannot_rewind_or_loop(payload, after):
    with httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as client:
        with pytest.raises(SourceError):
            ApiCycleSource(client).fetch_page('606', after=after)


def test_secrets_only_resolve_dedicated_namespace(monkeypatch):
    from ingest.telemetry.http_source import configured_client
    monkeypatch.setenv('TELEMETRY_ALLOWED_ORIGINS', 'http://machine.test')
    monkeypatch.setenv('TELEMETRY_ALLOW_HTTP', 'true')
    monkeypatch.setenv('TELEMETRY_SECRET_PRESS', 'synthetic-private-token')
    monkeypatch.setenv('SESSION_SECRET', 'never-a-source-token')
    with configured_client('http://machine.test', 'PRESS') as client:
        assert client.headers['Authorization'] == 'Bearer synthetic-private-token'
    with pytest.raises(SourceError, match='secret_unavailable'):
        configured_client('http://machine.test', 'SESSION_SECRET')
