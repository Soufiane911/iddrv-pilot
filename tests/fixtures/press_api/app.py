"""External synthetic source for QA only. Never mounted in the product API.

Run: uvicorn tests.fixtures.press_api.app:app --host 0.0.0.0 --port 8090
A SQLite file retains stream identity/events across source process restarts.
Private controls are limited to this standalone test double.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import asyncio
import json
import os
import secrets
import sqlite3
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Literal

DB_PATH = os.getenv('PRESS_FIXTURE_DB', '/tmp/press-fixture.sqlite')


def database():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY,payload TEXT)')
    conn.execute("INSERT OR IGNORE INTO meta VALUES('stream',?)", ('synthetic-' + uuid4().hex,))
    conn.commit()
    return conn


def emit(n):
    with database() as conn:
        stream = conn.execute("SELECT value FROM meta WHERE key='stream'").fetchone()[0]
        sequence = conn.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
        start = datetime.fromisoformat(metadata(conn, 'start_at', '2026-09-05T00:00:12+00:00'))
        profile = metadata(conn, 'profile', 'partial')
        for i in range(sequence + 1, sequence + n + 1):
            item = {'event_id': f'{stream}:{i}', 'sequence': i, 'machine_id': '606', 'cycle_counter': i,
                    'cycle_ended_at': (datetime.now(timezone.utc) if os.getenv('PRESS_FIXTURE_REALTIME') == 'true' else start + timedelta(seconds=12*(i-1))).isoformat(),
                    'measurements': {'cycle_time_s': 12.0, 'injection_time_s': .77}}
            if profile == 'complete':
                # Synthetic engineering values, already in canonical transport units.
                item['measurements'].update(cooling_time_s=6+.02*(i%5), peak_pressure_bar=800+2*(i%7),
                    clamp_force_kn=1400+3*(i%3), mold_temperature_c=55+.1*(i%4),
                    barrel_temp_zone2_c=220+.2*(i%6), energy_kwh=.8+.01*(i%5))
            conn.execute('INSERT INTO events VALUES(?,?)', (i, json.dumps(item)))
    return sequence + n


@asynccontextmanager
async def lifespan(app):
    async def live():
        while True:
            await asyncio.sleep(12)
            emit(1)
    task = asyncio.create_task(live()) if os.getenv('PRESS_FIXTURE_REALTIME') == 'true' else None
    yield
    if task:
        task.cancel()


app = FastAPI(lifespan=lifespan)


def metadata(conn, key, default=None):
    row = conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return row[0] if row else default


def check_machine(machine_id):
    if machine_id != '606':
        raise HTTPException(404, 'machine_not_found')


@app.get('/v1/machines/{machine_id}/cycles')
def cycles(machine_id: str, after: str | None = None, limit: int = Query(100, ge=1, le=500)):
    check_machine(machine_id)
    with database() as conn:
        delay = float(metadata(conn, 'delay_s', '0'))
        if delay:
            time.sleep(delay)
        error = int(metadata(conn, 'error', '0'))
        if error:
            return JSONResponse({'error': 'cursor_expired' if error == 410 else 'synthetic_error'}, status_code=error, headers={'Retry-After': '2'})
        stream = metadata(conn, 'stream')
        retention_floor = int(metadata(conn, 'retention_floor', '0'))
        position = 0
        if after:
            try:
                prefix, value = after.rsplit(':', 1)
                if prefix != stream:
                    raise ValueError()
                position = int(value)
            except ValueError:
                return JSONResponse({'error': 'cursor_invalid'}, status_code=400)
            if position < max(0, retention_floor - 1):
                return JSONResponse({'error': 'cursor_expired'}, status_code=410)
        rows = conn.execute('SELECT payload FROM events WHERE sequence>? AND sequence>=? ORDER BY sequence LIMIT ?', (position, retention_floor, limit+1)).fetchall()
        items = [json.loads(row[0]) for row in rows[:limit]]
        return {'schema_version': 1, 'stream_id': stream, 'items': items, 'next_cursor': f"{stream}:{items[-1]['sequence']}" if items else after, 'has_more': len(rows)>limit}


@app.get('/v1/machines/{machine_id}/status')
def status(machine_id: str):
    check_machine(machine_id)
    with database() as conn:
        floor = int(metadata(conn, 'retention_floor', '0'))
        row = conn.execute('SELECT payload FROM events WHERE sequence>=? ORDER BY sequence LIMIT 1', (floor,)).fetchone()
        return {'schema_version': 1, 'stream_id': metadata(conn, 'stream'), 'machine_id': machine_id,
                'observed_at': datetime.now(timezone.utc).isoformat(), 'machine_state': 'unknown',
                'last_cycle_sequence': conn.execute('SELECT max(sequence) FROM events WHERE sequence>=?', (floor,)).fetchone()[0],
                'oldest_available_sequence': floor if row else None,
                'oldest_available_at': json.loads(row[0])['cycle_ended_at'] if row else None}


class Control(BaseModel):
    emit: int = Field(default=0, ge=0, le=1000)
    error: int = Field(default=0, ge=0, le=599)
    retention_floor: int = Field(default=0, ge=0)
    delay_s: float = Field(default=0, ge=0, le=10)
    reset_stream: bool = False
    malformed: str | None = None
    profile: Literal['partial','complete'] | None = None
    start_at: datetime | None = None

    @field_validator('start_at')
    @classmethod
    def aware_start(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('timezone_required')
        return value


@app.post('/__test/control')
def control(value: Control, x_test_control_token: str = Header(default='')):
    expected = os.getenv('PRESS_FIXTURE_CONTROL_TOKEN', '')
    if not expected or not secrets.compare_digest(expected, x_test_control_token):
        raise HTTPException(404, 'not_found')
    with database() as conn:
        if value.reset_stream:
            # Explicit destructive reinitialization is confined to the test source.
            conn.execute("UPDATE meta SET value=? WHERE key='stream'", ('synthetic-' + uuid4().hex,))
        for key in ('profile', 'start_at'):
            item = getattr(value,key)
            if item is not None:
                conn.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key,item.isoformat() if isinstance(item,datetime) else item))
        for key in ('error', 'retention_floor', 'delay_s'):
            conn.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, str(getattr(value, key))))
    last = emit(value.emit)
    if value.malformed:
        with database() as conn:
            row = conn.execute('SELECT payload FROM events WHERE sequence=?', (last,)).fetchone()
            if row:
                item = json.loads(row[0])
                if value.malformed == 'wrong_machine':
                    item['machine_id'] = 'wrong-machine'
                elif value.malformed == 'date':
                    item['cycle_ended_at'] = 'invalid'
                elif value.malformed == 'late':
                    item['cycle_ended_at'] = '2026-09-01T00:00:00Z'
                elif value.malformed == 'counter_reset':
                    item['cycle_counter'] = 0
                else:
                    item['measurements']['cycle_time_s'] = {'nan': 'NaN', 'infinite': 'Infinity', 'unit': '12 milliseconds'}.get(value.malformed, 'invalid')
                conn.execute('UPDATE events SET payload=? WHERE sequence=?', (json.dumps(item), last))
    return {'last_sequence': last}
