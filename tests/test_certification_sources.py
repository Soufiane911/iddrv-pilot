import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from scripts.certification.sources.collect import SourceError, collect, parse
from scripts.certification.sources.database import extract


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', 'http://169.254.169.254/')
            self.end_headers()
            return
        if self.path == '/quota':
            self.send_response(429)
            self.end_headers()
            return
        if self.path == '/denied':
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'secret-remote-body')
            return
        self.send_response(200)
        self.end_headers()
        if self.path == '/html':
            body = b'<table><tr><th>id</th></tr><tr><td>1</td></tr></table>'
        elif self.path == '/bad':
            body = b'{'
        elif self.path == '/large':
            body = b'x' * 200
        else:
            body = json.dumps({'items': [{'id': 1, 'token': 'must-not-export'}], 'next': self.server.base + '/end' if self.path == '/start' else None}).encode()
        self.wfile.write(body)


class Sources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def spec(self, path='/start', **kwargs):
        return {'id': 'fixture', 'kind': 'rest', 'fields': ['id'], 'url': self.server.base + path,
                'allowed_urls': [self.server.base + p for p in ['/start', '/end', '/denied', '/html', '/bad', '/large', '/redirect', '/quota']],
                'local_fixture': True, **kwargs}

    def test_pagination_provenance_auth_redacted(self):
        with patch.dict(os.environ, {'CERT_TEST_TOKEN': 'secret-test-token'}):
            data, manifest = collect(self.spec(token_env='CERT_TEST_TOKEN'))
        self.assertEqual(manifest['rows'], 2)
        self.assertEqual(len(manifest['pages']), 2)
        self.assertEqual(manifest['output_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest['classification'], 'local_fixture')
        self.assertNotIn('secret', json.dumps(manifest))
        self.assertNotIn(b'token', data)
        self.assertNotIn('http', json.dumps(manifest))

    def test_limits_and_bad(self):
        for spec in [self.spec(max_pages=1), self.spec(max_rows=1), self.spec('/large', max_bytes=10), self.spec('/bad'), self.spec(timeout_s=0), self.spec('/start', local_fixture=False)]:
            with self.subTest(spec=spec), self.assertRaises(SourceError):
                collect(spec)

    def test_unauthorized_is_safe(self):
        with self.assertRaisesRegex(SourceError, '^http_401$'):
            collect(self.spec('/denied'))

    def test_html(self):
        data, manifest = collect(self.spec('/html', kind='html'))
        self.assertEqual(data, b'{"id":"1"}\n')
        self.assertEqual(manifest['rows'], 1)

    def test_empty_and_malformed(self):
        self.assertEqual(parse(b'[]', 'json', ['id']), [])
        self.assertEqual(parse(b'id\n', 'csv', ['id']), [])
        for raw, kind in [(b'', 'json'), (b'{', 'json'), (b'[{"x":1}]', 'json'), (b'id\n1,2', 'csv'), (b'<table>', 'html')]:
            with self.subTest(raw=raw), self.assertRaises(SourceError):
                parse(raw, kind, ['id'])

    def test_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.csv'
            path.write_text('id\n1\n')
            data, manifest = collect({'id': 'file', 'kind': 'csv', 'fields': ['id'], 'path': str(path), 'local_fixture': True})
            self.assertEqual(manifest['rows'], 1)
            self.assertNotIn(folder, json.dumps(manifest))

    def test_url_allowlist(self):
        spec = self.spec()
        spec['allowed_urls'] = []
        with self.assertRaisesRegex(SourceError, 'url_not_allowed'):
            collect(spec)

    def test_redirect_quota_timeout_cycle(self):
        for path, code in [('/redirect', 'http_302'), ('/quota', 'http_429')]:
            with self.assertRaisesRegex(SourceError, code):
                collect(self.spec(path))
        with patch('socket.create_connection', side_effect=TimeoutError('secret-host')):
            with self.assertRaisesRegex(SourceError, '^transport$'):
                collect(self.spec())
        with patch('scripts.certification.sources.collect.fetch', return_value=json.dumps({'items': [], 'next': self.server.base + '/start'}).encode()):
            with self.assertRaisesRegex(SourceError, 'pagination_cycle'):
                collect(self.spec())

    def test_sql_injection(self):
        with self.assertRaisesRegex(ValueError, 'invalid_scope'):
            extract(None, '1; DROP TABLE machines', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z')

    def test_duckdb_real(self):
        try:
            import duckdb  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name != 'duckdb':
                raise
            self.skipTest('Optional DuckDB absent: install scripts/certification/requirements-analytics.txt')
        from scripts.certification.sources.analytics import extract as analytics
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cycles.jsonl'
            path.write_text('\n'.join(json.dumps({'site_id': site, 'machine_id': 1, 'time': '2026-09-01T00:00:00Z', 'cycle_time_s': 10, 'data_quality_status': 'valid'}) for site in [1, 1, 2]))
            result = analytics(path, 1, '2026-09-01T00:00:00Z', '2026-09-02T00:00:00Z')
            self.assertEqual(result['rows'][0]['cycle_count'], 2)
            offset_result = analytics(path, 1, '2026-09-01T02:00:00+02:00', '2026-09-01T20:00:00-04:00')
            self.assertEqual(offset_result['rows'], result['rows'])
            print('DuckDB real:', result)


if __name__ == '__main__':
    unittest.main()
