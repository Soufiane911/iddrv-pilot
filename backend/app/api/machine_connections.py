from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

from .. import config
from ..connection_repository import ConnectionConflict, get_connection_config, local_machine, record_test, save_connection
from ..security import Identity, get_current_identity, require_site, require_site_roles
from ingest.telemetry.http_source import ApiCycleSource, SourceError, configured_client, validate_origin

router = APIRouter(prefix='/api/v1/machines', tags=['connections'])


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = Field(min_length=1, max_length=2048)
    external_machine_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,128}$')
    secret_ref: str | None = Field(default=None, pattern=r'^[A-Z][A-Z0-9_]{0,63}$')
    poll_interval_s: int = Field(default=1, ge=1, le=60)
    enabled: bool = False
    mapping_profile: Literal['iddrv-cycle-v1'] = 'iddrv-cycle-v1'


class ContinuityRecoveryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['resume_available', 'initialize_new_stream']
    expected_stream_id: str = Field(min_length=1, max_length=256)
    expected_cursor: str | None = Field(default=None, max_length=512)
    new_stream_id: str = Field(min_length=1, max_length=256)
    available_from_sequence: int | None = Field(default=None, ge=0)
    resume_cursor: str | None = Field(default=None, max_length=512)
    confirmation: Literal['I understand the gap and retained history']


def authorized_machine(machine_id, identity, write=False):
    machine = local_machine(machine_id)
    if not machine:
        raise HTTPException(404, 'machine_not_found')
    if machine.get('site_lifecycle_status') == 'archived':
        raise HTTPException(409, 'site_archived')
    if machine.get('machine_lifecycle_status') == 'archived':
        raise HTTPException(409, 'machine_archived')
    if write:
        require_site_roles(identity, machine['site_id'], 'supervisor', 'admin')
    else:
        require_site(identity, machine['site_id'])
    return machine


def checked_payload(payload):
    try:
        body = payload.model_dump()
        body['base_url'] = validate_origin(body['base_url'], config.settings.telemetry_allowed_origins, config.settings.telemetry_allow_http)
        return body
    except SourceError as exc:
        raise HTTPException(422, exc.code) from None


def source_status(base_url: str, secret_ref: str | None, external_machine_id: str) -> dict | None:
    """Read source identity and retention; never infer either from local latest."""
    try:
        with configured_client(base_url, secret_ref) as client:
            return ApiCycleSource(client).fetch_status(external_machine_id)
    except (SourceError, ValueError, TypeError):
        return None


def available_sequence(base_url: str, secret_ref: str | None, external_machine_id: str) -> int | None:
    status = source_status(base_url, secret_ref, external_machine_id)
    value = status.get('oldest_available_sequence') if status else None
    return int(value) if value is not None and int(value) >= 0 else None


@router.get('/{machine_id}/connection')
def read(machine_id: int, identity: Identity = Depends(get_current_identity)):
    authorized_machine(machine_id, identity)
    return get_connection_config(machine_id)


@router.put('/{machine_id}/connection')
def configure(machine_id: int, payload: ConnectionInput, identity: Identity = Depends(get_current_identity)):
    machine = authorized_machine(machine_id, identity, True)
    body = checked_payload(payload)
    try:
        return save_connection(machine, body)
    except ConnectionConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError:
        raise HTTPException(409, 'source_reference_already_connected') from None


@router.post('/{machine_id}/connection/test')
def test(machine_id: int, payload: ConnectionInput, identity: Identity = Depends(get_current_identity)):
    authorized_machine(machine_id, identity, True)
    body = checked_payload(payload)
    try:
        with configured_client(body['base_url'], body['secret_ref']) as client:
            source = ApiCycleSource(client)
            status = source.fetch_status(body['external_machine_id'])
            page = source.fetch_page(body['external_machine_id'], after=None, limit=1)
            if page.stream_id != status['stream_id']:
                raise SourceError('stream_changed', state='gap_detected')
            result = {'ok': True, 'state': 'reachable', 'mapping_profile': body['mapping_profile'],
                      'oldest_available_at': status['oldest_available_at'], 'source_state': status['machine_state'],
                      'stream_id': page.stream_id, 'sample_valid': all(i.rejection_reason is None for i in page.items),
                      'sample_rejections': [i.rejection_reason for i in page.items if i.rejection_reason]}
    except SourceError as exc:
        result = {'ok': False, 'state': exc.state, 'public_error': exc.code}
    record_test(machine_id, result)
    return result


@router.get('/{machine_id}/connection/continuity')
def continuity(machine_id: int, identity: Identity = Depends(get_current_identity)):
    """Expose the evidence needed before a supervisor can resolve a gap."""
    machine = authorized_machine(machine_id, identity)
    from ..db import get_connection
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT c.id,c.state,c.public_error,c.external_machine_id,c.base_url,c.secret_ref,
                              o.stream_id,o.cursor,o.last_sequence,o.committed_at,
                              c.last_cycle_at,c.last_response_at,
                              c.last_test_result->>'oldest_available_at' AS oldest_available_at
                       FROM machine_connections c LEFT JOIN machine_stream_offsets o ON o.connection_id=c.id
                       WHERE c.machine_id=%s''', (machine_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'connection_not_found')
        cur.execute('''SELECT id,previous_stream_id,new_stream_id,last_validated_cursor,
                              last_validated_sequence,available_from_sequence,decision,confirmation,created_at
                       FROM continuity_recovery_reviews WHERE connection_id=%s ORDER BY created_at DESC LIMIT 10''', (row['id'],))
        reviews = [dict(item) for item in cur.fetchall()]
    from_source = available_sequence(row['base_url'], row['secret_ref'], row['external_machine_id']) if row['state'] == 'gap_detected' else None
    return {'machine_id': machine['id'], 'state': row['state'], 'public_error': row['public_error'],
            'last_validated': {'stream_id': row['stream_id'], 'cursor': row['cursor'], 'sequence': row['last_sequence'], 'at': row['committed_at']},
            'available_history': {'oldest_available_at': row['oldest_available_at'], 'from_sequence': from_source},
            'source_reference': row['external_machine_id'], 'reviews': reviews,
            'automatic_latest_jump': False}


@router.post('/{machine_id}/connection/continuity/recover')
def recover_continuity(machine_id: int, payload: ContinuityRecoveryInput, identity: Identity = Depends(get_current_identity)):
    machine = authorized_machine(machine_id, identity, True)
    if identity.role not in ('supervisor', 'admin'):
        raise HTTPException(403, 'insufficient_role')
    try:
        actor_id = UUID(identity.user_id)
    except (ValueError, TypeError):
        raise HTTPException(422, 'actor_identity_invalid') from None
    from ..db import get_connection
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Lock the connection and offset independently. PostgreSQL rejects
        # `FOR UPDATE` on the nullable side of this LEFT JOIN.
        cur.execute('''SELECT c.id,c.state,c.base_url,c.secret_ref,c.external_machine_id
                       FROM machine_connections c WHERE c.machine_id=%s FOR UPDATE''', (machine_id,))
        current = cur.fetchone()
        if not current:
            raise HTTPException(404, 'connection_not_found')
        cur.execute('''SELECT stream_id,cursor,last_sequence
                       FROM machine_stream_offsets WHERE connection_id=%s FOR UPDATE''', (current['id'],))
        offset = cur.fetchone()
        current.update(dict(offset) if offset else {'stream_id': None, 'cursor': None, 'last_sequence': None})
        if current['state'] != 'gap_detected':
            raise HTTPException(409, 'continuity_review_required')
        if current['stream_id'] != payload.expected_stream_id or current['cursor'] != payload.expected_cursor:
            raise HTTPException(409, 'continuity_confirmation_stale')
        if payload.decision == 'resume_available':
            if payload.new_stream_id != current['stream_id'] or not payload.resume_cursor:
                raise HTTPException(422, 'resume_cursor_required')
            server_status = source_status(current['base_url'], current['secret_ref'], current['external_machine_id'])
            server_stream = server_status.get('stream_id') if server_status else None
            if server_stream != current['stream_id']:
                raise HTTPException(409, 'continuity_stream_changed')
            server_available = server_status.get('oldest_available_sequence') if server_status else None
            server_available = int(server_available) if server_available is not None and int(server_available) >= 0 else None
            if server_available is None:
                raise HTTPException(409, 'continuity_available_history_unverifiable')
            if payload.available_from_sequence != server_available:
                raise HTTPException(409, 'continuity_available_history_changed')
            if payload.available_from_sequence is not None:
                try:
                    resume_stream, sequence_text = payload.resume_cursor.rsplit(':', 1)
                    resumed_sequence = int(sequence_text)
                except (ValueError, IndexError):
                    raise HTTPException(422, 'resume_cursor_invalid') from None
                if resume_stream != current['stream_id']:
                    raise HTTPException(409, 'continuity_resume_stream_mismatch')
                if resumed_sequence >= payload.available_from_sequence:
                    raise HTTPException(422, 'resume_cursor_must_precede_available_history')
        elif payload.new_stream_id == current['stream_id']:
            raise HTTPException(422, 'new_stream_identity_required')
        cur.execute('''INSERT INTO continuity_recovery_reviews
                       (connection_id,site_id,machine_id,actor_user_id,previous_stream_id,new_stream_id,
                        last_validated_cursor,last_validated_sequence,available_from_sequence,decision,confirmation)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (current['id'], machine['site_id'], machine_id, str(actor_id), current['stream_id'], payload.new_stream_id,
                     current['cursor'], current['last_sequence'], payload.available_from_sequence, payload.decision, payload.confirmation))
        if current['stream_id'] is None:
            cur.execute('''INSERT INTO machine_stream_offsets(connection_id,stream_id,cursor,last_sequence,committed_at)
                           VALUES(%s,%s,%s,%s,now())''', (current['id'], payload.new_stream_id, payload.resume_cursor, None))
        else:
            cur.execute('''UPDATE machine_stream_offsets SET stream_id=%s,cursor=%s,last_sequence=%s,committed_at=now()
                           WHERE connection_id=%s''', (payload.new_stream_id, payload.resume_cursor, None if payload.decision == 'initialize_new_stream' else int(payload.resume_cursor.rsplit(':', 1)[1]), current['id']))
        cur.execute('''UPDATE machine_connections SET state='configured',enabled=true,public_error=NULL,
                       failure_count=0,next_poll_at=now(),updated_at=now() WHERE id=%s
                       RETURNING id,state,enabled''', (current['id'],))
        result = dict(cur.fetchone())
    return {'ok': True, 'state': result['state'], 'enabled': result['enabled'], 'decision': payload.decision,
            'stream_id': payload.new_stream_id, 'history_gap_preserved': True, 'automatic_latest_jump': False}
