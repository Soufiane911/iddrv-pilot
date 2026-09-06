"""Bounded HTTP reader for the external press contract. No product API dependency."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
import json
import math
import os
import re
from urllib.parse import quote, urlsplit

import httpx

from .models import CycleEnvelope, CyclePage

# Canonical column mapping and PostgreSQL numeric ranges, excluding unknown fields.
MEASUREMENTS = {
    **{k: (k, 10000) for k in ('cycle_time_s', 'dosing_time_s', 'injection_time_s', 'cooling_time_s', 'mold_open_time_s')},
    **{k: (k, 1000) for k in ('cushion_mm',)},
    'switchover_position_mm': ('switchover_position', 1000),
    **{k: (k, 1000000) for k in ('switchover_pressure_bar', 'peak_pressure_bar', 'clamp_force_kn', 'energy_kwh')},
    **{k: (k, 10000) for k in ('barrel_temp_zone1_c', 'barrel_temp_zone2_c', 'barrel_temp_zone3_c', 'mold_temperature_c', 'oil_temperature_c')},
}
MAX_BYTES = 2 * 1024 * 1024


class SourceError(ValueError):
    def __init__(self, code: str, *, state='contract_error', retryable=False, retry_after=None, response_received=False):
        super().__init__(code)
        self.code, self.state = code, state
        self.retryable, self.retry_after = retryable, retry_after
        self.response_received = response_received


def validate_origin(url: str, allowed_origins: tuple[str, ...], allow_http=False) -> str:
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        raise SourceError('origin_not_allowed', state='configuration_error') from None
    if (parsed.scheme not in ('https', 'http') or (parsed.scheme == 'http' and not allow_http)
            or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or any(c.isspace() for c in url)):
        raise SourceError('origin_not_allowed', state='configuration_error')
    origin = f'{parsed.scheme}://{parsed.netloc.lower()}'
    if origin not in {v.rstrip('/').lower() for v in allowed_origins}:
        raise SourceError('origin_not_allowed', state='configuration_error')
    return origin


def configured_client(base_url: str, secret_ref: str | None = None) -> httpx.Client:
    allowed = tuple(v.strip() for v in os.getenv('TELEMETRY_ALLOWED_ORIGINS', '').split(',') if v.strip())
    origin = validate_origin(base_url, allowed, os.getenv('TELEMETRY_ALLOW_HTTP', 'false').lower() == 'true')
    headers = {}
    if secret_ref:
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', secret_ref):
            raise SourceError('secret_reference_invalid', state='configuration_error')
        # Only the dedicated telemetry namespace can be resolved, never arbitrary env keys.
        secret = os.getenv('TELEMETRY_SECRET_' + secret_ref)
        if not secret:
            raise SourceError('secret_unavailable', state='configuration_error')
        headers['Authorization'] = 'Bearer ' + secret
    return httpx.Client(base_url=origin, headers=headers, trust_env=False, follow_redirects=False,
                        timeout=httpx.Timeout(5.0, connect=2.0))


def _text(value, code):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise SourceError(code)
    return value


def _date(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        raise SourceError('cycle_date_invalid') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise SourceError('cycle_timezone_required')
    return result


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise SourceError('measurement_non_finite')
    if isinstance(value, dict):
        for item in value.values():
            _finite_tree(item)
    if isinstance(value, list):
        for item in value:
            _finite_tree(item)


def validate_page(payload: dict, *, expected_machine_id: str, expected_stream_id: str | None) -> CyclePage:
    if not isinstance(payload, dict) or type(payload.get('schema_version')) is not int or payload['schema_version'] != 1:
        raise SourceError('schema_version_invalid')
    stream = _text(payload.get('stream_id'), 'stream_id_invalid')
    if expected_stream_id is not None and stream != expected_stream_id:
        raise SourceError('stream_changed', state='gap_detected')
    rows, more, cursor = payload.get('items'), payload.get('has_more'), payload.get('next_cursor')
    if not isinstance(rows, list) or len(rows) > 500 or type(more) is not bool:
        raise SourceError('page_envelope_invalid')
    if cursor is not None:
        _text(cursor, 'cursor_invalid')
    if (more or rows) and cursor is None or more and not rows:
        raise SourceError('cursor_invalid')
    items, previous, ids = [], -1, set()
    for row in rows:
        if not isinstance(row, dict):
            raise SourceError('event_identity_invalid')
        event = _text(row.get('event_id'), 'event_identity_invalid')
        sequence = row.get('sequence')
        if type(sequence) is not int or sequence <= previous or sequence > 9223372036854775807 or event in ids:
            raise SourceError('sequence_invalid')
        if row.get('machine_id') != expected_machine_id:
            raise SourceError('machine_identity_mismatch')
        previous = sequence
        ids.add(event)
        date, counter, measurements, reason = None, None, {}, None
        try:
            date = _date(row.get('cycle_ended_at'))
            counter = row.get('cycle_counter')
            if type(counter) is not int or not 0 <= counter <= 9223372036854775807:
                raise SourceError('cycle_counter_invalid')
            measurements = row.get('measurements')
            if not isinstance(measurements, dict):
                raise SourceError('measurements_invalid')
            _finite_tree(row)
            for key, (_, maximum) in MEASUREMENTS.items():
                value = measurements.get(key)
                if value is None:
                    continue
                # _finite_tree has already rejected non-finite floats. Compare
                # integers directly: math.isfinite coerces huge ints to float.
                if type(value) not in (int, float) or abs(value) >= maximum:
                    raise SourceError('measurement_invalid')
                if key.endswith('_s') and value < 0:
                    raise SourceError('measurement_invalid')
                scale = 2
                if key.endswith('_s') or key in ('cushion_mm', 'switchover_position_mm'):
                    scale = 3
                elif key == 'energy_kwh':
                    scale = 4
                # PostgreSQL NUMERIC rounds to its declared scale before its
                # range check. Keep that rule without modifying the raw value.
                rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
                if abs(rounded) >= maximum:
                    raise SourceError('measurement_invalid')
        except SourceError as exc:
            reason = exc.code
        items.append(CycleEnvelope(event, sequence, row, date, counter, measurements or {}, reason))
    return CyclePage(stream, items, cursor, more, expected_machine_id)


class ApiCycleSource:
    def __init__(self, client: httpx.Client):
        self.client = client

    def _get(self, path, params=None):
        try:
            with self.client.stream('GET', path, params=params, follow_redirects=False,
                                    timeout=httpx.Timeout(5.0, connect=2.0)) as response:
                status = response.status_code
                if status != 200:
                    if status in (401, 403):
                        raise SourceError('source_access_denied', state='access_error', response_received=True)
                    if status == 404:
                        raise SourceError('source_machine_not_found', state='configuration_error', response_received=True)
                    if status == 410:
                        raise SourceError('cursor_expired', state='gap_detected', response_received=True)
                    if status == 429 or status >= 500:
                        retry = None
                        raw = response.headers.get('Retry-After', '')
                        if raw:
                            try:
                                retry = float(raw)
                            except ValueError:
                                try:
                                    retry = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
                                except (ValueError, TypeError):
                                    pass
                        raise SourceError('source_busy' if status == 429 else 'source_unavailable', state='retrying', retryable=True, response_received=True,
                                          retry_after=max(1, min(30, retry)) if retry is not None and math.isfinite(retry) else None)
                    raise SourceError('source_http_contract_error', response_received=True)
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise SourceError('response_too_large', response_received=True)
                try:
                    return json.loads(data)
                except (ValueError, UnicodeError):
                    raise SourceError('response_json_invalid', response_received=True) from None
        except httpx.TimeoutException:
            raise SourceError('source_timeout', state='retrying', retryable=True) from None
        except httpx.HTTPError:
            raise SourceError('source_unavailable', state='retrying', retryable=True) from None

    def fetch_page(self, machine_id: str, *, after: str | None, limit: int = 100) -> CyclePage:
        if not 1 <= limit <= 500:
            raise SourceError('limit_invalid')
        params = {'limit': limit}
        if after is not None:
            params['after'] = after
        payload = self._get(f'/v1/machines/{quote(machine_id, safe="")}/cycles', params)
        try:
            page = validate_page(payload, expected_machine_id=machine_id, expected_stream_id=None)
            if page.items and page.next_cursor == after or not page.items and after is not None and page.next_cursor != after:
                raise SourceError('cursor_not_progressive')
            return replace(page, after=after)
        except SourceError as exc:
            exc.response_received = True
            raise

    def fetch_status(self, machine_id: str) -> dict:
        value = self._get(f'/v1/machines/{quote(machine_id, safe="")}/status')
        if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('machine_id') != machine_id or value.get('machine_state') not in ('running', 'stopped', 'unknown'):
            raise SourceError('status_invalid')
        _text(value.get('stream_id'), 'stream_id_invalid')
        _date(value.get('observed_at'))
        if value.get('oldest_available_at') is not None:
            _date(value['oldest_available_at'])
        return {key: value.get(key) for key in ('stream_id', 'machine_state', 'observed_at', 'oldest_available_at', 'oldest_available_sequence', 'last_cycle_sequence')}
