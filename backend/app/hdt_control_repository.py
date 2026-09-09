"""Persistent, conservative HDT control state.  This module never selects a model."""
from psycopg2.extras import Json, RealDictCursor
from .db import get_connection


def _read(cur, machine_id):
    cur.execute("""SELECT machine_id,desired_state,effective_state,blocking_reasons,model_profile,updated_by,updated_at
                   FROM machine_hdt_controls WHERE machine_id=%s""", (machine_id,))
    row = cur.fetchone()
    if row:
        result = dict(row)
        # PostgreSQL jsonb is normally decoded by psycopg2, but the boundary
        # remains safe for test drivers and old installations.
        if not isinstance(result.get('blocking_reasons'), list):
            result['blocking_reasons'] = []
        return result
    return {'machine_id': machine_id, 'desired_state': 'stopped', 'effective_state': 'stopped',
            'blocking_reasons': [], 'model_profile': None, 'updated_by': None, 'updated_at': None}


def get_control(machine_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        return _read(cur, machine_id)


def set_control(machine: dict, desired: str, actor: str):
    """Set intent and effective admission atomically with the press lock.

    ``summary6_replay`` is deliberately not live HDT.  Only the explicit
    historical runtime can admit the worker; all other modes remain visible as
    a requested active intent with an effective blocked state.
    """
    from ml.runtime_mode import historical_enabled

    machine_id = int(machine['id'])
    site_id = int(machine['site_id'])
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Lifecycle writers lock site first, then the press advisory lock.
        # Collection follows the same order; stop therefore linearizes before
        # a queued write while the scorer's press lock prevents claim/finish.
        cur.execute('SELECT status FROM sites WHERE id=%s FOR UPDATE', (site_id,))
        site = cur.fetchone()
        if not site or site['status'] == 'archived':
            raise RuntimeError('site_archived')
        cur.execute('SELECT pg_advisory_xact_lock(1347568468,%s)', (machine_id,))
        cur.execute('SELECT status FROM machines WHERE id=%s AND site_id=%s FOR UPDATE', (machine_id, site_id))
        current_machine = cur.fetchone()
        if not current_machine:
            raise RuntimeError('machine_not_found')
        if current_machine['status'] == 'archived':
            raise RuntimeError('machine_archived')

        reasons: list[str] = []
        if desired == 'active':
            cur.execute("""SELECT state,enabled,mapping_profile
                           FROM machine_connections WHERE machine_id=%s FOR UPDATE""", (machine_id,))
            source = cur.fetchone()
            if not source or not source['enabled'] or source['state'] != 'collecting':
                reasons.append('source_not_ready')
            if not source or not source['enabled'] or source['mapping_profile'] != 'iddrv-cycle-v1':
                reasons.append('input_contract_unrecognized')
            if not historical_enabled():
                reasons.append('model_profile_not_enabled')
            effective = 'blocked' if reasons else 'active'
        else:
            effective = 'stopped'

        cur.execute("""INSERT INTO machine_hdt_controls
          (machine_id,site_id,desired_state,effective_state,blocking_reasons,model_profile,updated_by)
          VALUES(%s,%s,%s,%s,%s,NULL,%s)
          ON CONFLICT(machine_id) DO UPDATE SET desired_state=EXCLUDED.desired_state,
          effective_state=EXCLUDED.effective_state,blocking_reasons=EXCLUDED.blocking_reasons,
          model_profile=NULL,updated_by=EXCLUDED.updated_by,updated_at=now()
          RETURNING machine_id,site_id,desired_state,effective_state,blocking_reasons,model_profile,updated_by,updated_at""",
          (machine_id, site_id, desired, effective, Json(reasons), actor))
        result = dict(cur.fetchone())
        cur.execute("""INSERT INTO machine_hdt_control_audit
          (machine_id,site_id,desired_state,effective_state,blocking_reasons,actor_id)
          VALUES(%s,%s,%s,%s,%s,%s)""",
          (machine_id, site_id, desired, effective, Json(reasons), actor))
        result.pop('site_id', None)
        return result
