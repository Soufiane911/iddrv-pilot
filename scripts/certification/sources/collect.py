"""Offline CLI collectors, never imported by the production API. Python stdlib."""
import csv
import hashlib
import http.client
import io
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class SourceError(ValueError):
    """Safe codes only: never include remote bodies, URLs or credentials."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None
        self.depth = 0
        self.tables = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.depth == 0:
                self.tables += 1
            self.depth += 1
            if self.depth > 1:
                raise SourceError('nested_table')
        if self.depth and self.tables == 1 and tag == 'tr':
            self.row = []
        if self.row is not None and tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == 'table':
            self.depth -= 1


def parse(raw, kind, fields):
    try:
        text = raw.decode('utf-8-sig')
        if kind == 'csv':
            reader = csv.DictReader(io.StringIO(text), strict=True)
            if reader.fieldnames != fields:
                raise SourceError('schema')
            rows = list(reader)
        elif kind == 'html':
            parser = Table()
            parser.feed(text)
            parser.close()
            if parser.depth or parser.row is not None or not parser.rows or parser.rows[0] != fields:
                raise SourceError('schema')
            if any(len(r) != len(fields) for r in parser.rows[1:]):
                raise SourceError('schema')
            rows = [dict(zip(fields, r)) for r in parser.rows[1:]]
        else:
            rows = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(SourceError('nonfinite')))
        if not isinstance(rows, list) or any(not isinstance(r, dict) or any(f not in r or r[f] is None or isinstance(r[f], (dict, list)) for f in fields) or None in r for r in rows):
            raise SourceError('schema')
        return [{f: r[f] for f in fields} for r in rows]
    except (UnicodeError, json.JSONDecodeError, csv.Error, TypeError):
        raise SourceError('malformed') from None


def fetch(url, spec, budget):
    """Pin validated DNS address; forbid redirects, proxies, URL credentials."""
    try:
        u = urlsplit(url)
        if url not in spec['allowed_urls'] or u.username or u.password or u.fragment:
            raise SourceError('url_not_allowed')
        local = spec.get('local_fixture', False)
        if u.scheme != 'https' and not (local and u.scheme == 'http'):
            raise SourceError('https_required')
        port = u.port or (443 if u.scheme == 'https' else 80)
        addresses = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)
        ips = [a[4][0] for a in addresses]
        if not ips or any(not (ipaddress.ip_address(ip).is_loopback if local else ipaddress.ip_address(ip).is_global) for ip in ips):
            raise SourceError('address_forbidden')
        timeout = spec.get('timeout_s', 5)
        conn = http.client.HTTPConnection(u.hostname, port, timeout=timeout)
        sock = socket.create_connection((ips[0], port), timeout=timeout)
        try:
            if u.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
            conn.sock = sock
            headers = {'User-Agent': 'IDDRV-certification-collector/1.0', 'Accept-Encoding': 'identity'}
            if spec.get('token_env'):
                token = os.environ.get(spec['token_env'])
                if not token or '\r' in token or '\n' in token:
                    raise SourceError('auth_configuration')
                headers['Authorization'] = 'Bearer ' + token
            conn.request('GET', u.path + ('?' + u.query if u.query else ''), headers=headers)
            response = conn.getresponse()
            if response.status != 200:
                raise SourceError('http_' + str(response.status))
            chunks = []
            start = time.monotonic()
            while True:
                chunk = response.read1(min(65536, budget + 1))
                if time.monotonic() - start > timeout:
                    raise SourceError('timeout')
                if not chunk:
                    break
                budget -= len(chunk)
                if budget < 0:
                    raise SourceError('byte_limit')
                chunks.append(chunk)
            return b''.join(chunks)
        finally:
            conn.close()
            sock.close()
    except SourceError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise SourceError('transport') from None


def collect(spec):
    """JSON contract: id, kind, fields, path/url and explicit finite limits."""
    if not re.fullmatch(r'[a-z0-9_-]{1,64}', spec.get('id', '')):
        raise SourceError('source_id')
    fields = spec.get('fields')
    if not isinstance(fields, list) or not fields or len(set(fields)) != len(fields) or any(not isinstance(f, str) or not re.fullmatch(r'[a-zA-Z0-9_ -]{1,64}', f) for f in fields):
        raise SourceError('fields')
    for key, default, ceiling in [('max_bytes', 1048576, 10485760), ('max_rows', 1000, 100000), ('max_pages', 3, 20), ('timeout_s', 5, 30)]:
        value = spec.get(key, default)
        if type(value) is not int or not 1 <= value <= ceiling:
            raise SourceError('limits')
    kind = spec.get('kind')
    if kind not in ('csv', 'json', 'rest', 'html'):
        raise SourceError('kind')
    budget, rows, pages = spec.get('max_bytes', 1048576), [], []
    url, seen = spec.get('url'), set()
    for page in range(spec.get('max_pages', 3)):
        if url:
            if url in seen:
                raise SourceError('pagination_cycle')
            seen.add(url)
            raw = fetch(url, spec, budget)
        else:
            if kind in ('rest', 'html'):
                raise SourceError('url_required')
            with Path(spec['path']).open('rb') as stream:
                raw = stream.read(budget + 1)
        budget -= len(raw)
        if budget < 0:
            raise SourceError('byte_limit')
        next_url = None
        if kind == 'rest':
            try:
                payload = json.loads(raw)
                next_url = payload.get('next')
                if next_url is not None and not isinstance(next_url, str):
                    raise SourceError('pagination_schema')
                batch = parse(canonical(payload['items']), 'json', fields)
            except (ValueError, KeyError, AttributeError, TypeError):
                raise SourceError('rest_schema') from None
        else:
            batch = parse(raw, kind, fields)
        rows.extend(batch)
        if len(rows) > spec.get('max_rows', 1000):
            raise SourceError('row_limit')
        pages.append({'page': page + 1, 'bytes': len(raw), 'rows': len(batch), 'sha256': hashlib.sha256(raw).hexdigest()})
        if not next_url:
            break
        url = next_url
    else:
        raise SourceError('page_limit')
    output = b''.join(canonical(r) + b'\n' for r in rows)
    manifest = {'version': 1, 'source_id': spec['id'], 'kind': kind,
                'classification': 'local_fixture' if spec.get('local_fixture') else spec.get('classification', 'operator_supplied'),
                'collected_at_utc': datetime.now(timezone.utc).isoformat(),
                'rows': len(rows), 'pages': pages, 'output_sha256': hashlib.sha256(output).hexdigest()}
    return output, manifest
