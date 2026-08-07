"""Read/write boundary for the G2 investigation API."""
from datetime import datetime
from uuid import UUID
from .db import get_connection


def _import_session(row, files):
    return {"id": row[0], "site_id": row[1], "name": row[2], "status": row[3], "summary": row[4] or {},
            "files": files, "created_at": row[5], "updated_at": row[6]}


def create_import_session(site_id: int, name: str, user_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO import_sessions(site_id,name,created_by)
                           VALUES (%s,%s,%s) RETURNING id,site_id,name,status,summary,created_at,updated_at""", (site_id, name, user_id))
            row = cur.fetchone(); conn.commit()
    return _import_session(row, [])


def get_import_session(session_id: UUID):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,site_id,name,status,summary,created_at,updated_at
                           FROM import_sessions WHERE id=%s""", (str(session_id),))
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute("""SELECT id,file_name,source_kind,mime_type,size_bytes,file_hash,status,profile
                           FROM import_session_files WHERE session_id=%s ORDER BY created_at""", (str(session_id),))
            files = [{"id": r[0], "file_name": r[1], "source_kind": r[2], "mime_type": r[3], "size_bytes": r[4],
                      "file_hash": r[5], "status": r[6], "profile": r[7] or {}} for r in cur.fetchall()]
    return _import_session(row, files)


def add_import_file(session_id: UUID, payload: dict):
    profile = {"columns": [], "recognized": [], "unknown": [], "confidence": 0.0,
               "message": "Profilage en attente du worker d’ingestion."}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO import_session_files(session_id,file_name,source_kind,mime_type,size_bytes,file_hash,profile)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (session_id,file_name,file_hash) DO NOTHING""",
                        (str(session_id), payload["file_name"], payload["source_kind"], payload.get("mime_type"),
                         payload.get("size_bytes", 0), payload.get("file_hash"), __import__("json").dumps(profile)))
            cur.execute("UPDATE import_sessions SET status='profiling', updated_at=NOW() WHERE id=%s", (str(session_id),))
            conn.commit()


def validate_import_session(session_id: UUID, user_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*)::int,
                          COUNT(*) FILTER (
                            WHERE file_hash IS NOT NULL
                              AND jsonb_array_length(COALESCE(profile->'columns', '[]'::jsonb)) > 0
                              AND status IN ('needs_review','validated')
                          )::int
                   FROM import_session_files WHERE session_id=%s""",
                (str(session_id),),
            )
            total, profiled = cur.fetchone()
            if total == 0 or profiled != total:
                raise ValueError("import_session_not_profiled")
            cur.execute(
                "UPDATE import_session_files SET status='validated' WHERE session_id=%s",
                (str(session_id),),
            )
            cur.execute(
                "UPDATE import_sessions SET status='validated', updated_at=NOW() WHERE id=%s",
                (str(session_id),),
            )
            conn.commit()
    return get_import_session(session_id)

def _incident(row):
    keys = ("id","site_id","machine_id","machine_erp_ref","production_order_id","status","severity","symptom","defect_type","started_at","ended_at","created_at","data_cutoff","confidence")
    return dict(zip(keys, row))

def list_incidents(site_id=None, start=None, end=None, status=None, machine_id=None, allowed_site_ids=None, limit=None, offset=0):
    clauses, args = [], []
    if site_id is not None: clauses.append("i.site_id=%s"); args.append(site_id)
    if machine_id is not None: clauses.append("i.machine_id=%s"); args.append(machine_id)
    if allowed_site_ids is not None:
        if not allowed_site_ids:
            return []
        clauses.append("i.site_id = ANY(%s)"); args.append(list(allowed_site_ids))
    if start is not None: clauses.append("i.started_at >= %s"); args.append(start)
    if end is not None: clauses.append("i.started_at <= %s"); args.append(end)
    if status is not None: clauses.append("i.status=%s"); args.append(status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = """SELECT i.id,i.site_id,i.machine_id,m.erp_ref,i.production_order_id,i.status,i.severity,i.symptom,i.defect_type,i.started_at,i.ended_at,i.created_at,i.data_cutoff,i.confidence FROM incidents i LEFT JOIN machines m ON m.id=i.machine_id""" + where + " ORDER BY i.started_at DESC"
    if limit is not None:
        sql += " LIMIT %s OFFSET %s"
        args.extend([limit, max(0, offset)])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args); return [_incident(r) for r in cur.fetchall()]

def get_incident(incident_id: UUID, allowed_site_ids=None):
    rows = list_incidents(allowed_site_ids=allowed_site_ids)
    return next((r for r in rows if str(r["id"]) == str(incident_id)), None)

def get_evidence(incident_id: UUID):
    sql = """SELECT e.id,e.source_kind,e.source_ref,e.metric,e.window_start,e.window_end,
                    e.observation,e.baseline,e.delta,e.supports,e.excerpt
             FROM diagnostic_evidence e
             JOIN diagnostic_runs r ON r.id=e.run_id
             WHERE r.id=(
                 SELECT latest.id FROM diagnostic_runs latest
                 WHERE latest.incident_id=%s AND latest.status='completed'
                 ORDER BY latest.completed_at DESC NULLS LAST,latest.started_at DESC
                 LIMIT 1
             )
             ORDER BY e.window_start"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(incident_id),)); rows=[]
            for r in cur.fetchall():
                rows.append(dict(id=r[0],source_kind=r[1],source_ref=r[2],metric=r[3],window={"start":r[4],"end":r[5]},observation=r[6],baseline=r[7],delta=float(r[8]) if r[8] is not None else None,supports=r[9],excerpt=r[10]))
            return rows

def save_feedback(incident_id: UUID, verdict: str, comment: str | None):
    sql="INSERT INTO feedback (incident_id,verdict,comment) VALUES (%s,%s,%s) RETURNING id,incident_id,verdict,comment"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql,(str(incident_id),verdict,comment)); row=cur.fetchone(); conn.commit()
            return dict(id=row[0],incident_id=row[1],verdict=row[2],comment=row[3])


def list_proposals(incident_id: UUID | None = None, allowed_site_ids=None):
    clauses, args = [], []
    if incident_id is not None:
        clauses.append("p.incident_id=%s"); args.append(str(incident_id))
    if allowed_site_ids is not None:
        if not allowed_site_ids:
            return []
        clauses.append("i.site_id=ANY(%s)"); args.append(list(allowed_site_ids))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = """SELECT p.id,p.incident_id,p.run_id,p.action_code,p.label,p.status,p.created_at
             FROM action_proposals p JOIN incidents i ON i.id=p.incident_id""" + where + " ORDER BY p.created_at DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
    return [dict(id=r[0], incident_id=r[1], run_id=r[2], action_code=r[3], label=r[4], status=r[5], created_at=r[6]) for r in rows]


def get_proposal(proposal_id: UUID, allowed_site_ids=None):
    clauses, args = ["p.id=%s"], [str(proposal_id)]
    if allowed_site_ids is not None:
        if not allowed_site_ids:
            return None
        clauses.append("i.site_id=ANY(%s)"); args.append(list(allowed_site_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT p.id,p.incident_id,p.run_id,p.action_code,p.label,p.status,p.created_at
                           FROM action_proposals p JOIN incidents i ON i.id=p.incident_id
                           WHERE """ + " AND ".join(clauses), args)
            row = cur.fetchone()
    if row is None:
        return None
    return dict(id=row[0], incident_id=row[1], run_id=row[2], action_code=row[3], label=row[4], status=row[5], created_at=row[6])


def create_proposal(incident_id: UUID, action_code: str, label: str, run_id: UUID | None = None):
    sql = """INSERT INTO action_proposals(incident_id,run_id,action_code,label)
             VALUES (%s,%s,%s,%s)
             ON CONFLICT (incident_id,action_code) DO UPDATE SET
               label=EXCLUDED.label,run_id=EXCLUDED.run_id
             WHERE action_proposals.status='proposed'
             RETURNING id,incident_id,run_id,action_code,label,status,created_at"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(incident_id), str(run_id) if run_id else None, action_code, label))
            row = cur.fetchone(); conn.commit()
    if row is None:
        return None
    return dict(id=row[0], incident_id=row[1], run_id=row[2], action_code=row[3], label=row[4], status=row[5], created_at=row[6])


def decide_proposal(proposal_id: UUID, user_id: str, status: str, reason: str | None):
    sql = """WITH decision AS (
               INSERT INTO action_proposal_decisions(proposal_id,decided_by,status,reason)
               SELECT p.id,%s,%s,%s FROM action_proposals p
               WHERE p.id=%s AND p.status='proposed'
               ON CONFLICT (proposal_id) DO NOTHING
               RETURNING id,proposal_id,status,reason,decided_at
             )
             UPDATE action_proposals p SET status=CASE WHEN %s='approved' THEN 'accepted' ELSE 'rejected' END
             FROM decision d WHERE p.id=d.proposal_id
             RETURNING d.id,d.proposal_id,d.status,d.reason,d.decided_at"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(user_id), status, reason, str(proposal_id), status))
            row = cur.fetchone(); conn.commit()
    if row is None:
        return None
    return dict(id=row[0], proposal_id=row[1], status=row[2], reason=row[3], decided_at=row[4])


def get_investigation(run_id: UUID, allowed_site_ids=None):
    clauses, args = ["r.id=%s"], [str(run_id)]
    if allowed_site_ids is not None:
        if not allowed_site_ids:
            return None
        clauses.append("i.site_id=ANY(%s)"); args.append(list(allowed_site_ids))
    where = " AND ".join(clauses)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id,r.incident_id,r.engine,r.status,r.started_at,r.completed_at,r.data_cutoff,r.result FROM diagnostic_runs r JOIN incidents i ON i.id=r.incident_id WHERE " + where, args)
            row = cur.fetchone()
    if row is None:
        return None
    return dict(id=row[0], incident_id=row[1], engine=row[2], status=row[3], started_at=row[4], completed_at=row[5], data_cutoff=row[6], result=row[7])

def persist_investigation(incident_id, result, as_of):
    """Persist engine output and return its run id (JSONB values are adapted by psycopg)."""
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO diagnostic_runs (incident_id,engine,status,completed_at,data_cutoff,result) VALUES (%s,'deterministic_local','completed',NOW(),%s,%s) RETURNING id", (str(incident_id), as_of, json.dumps(result.to_dict())))
            run_id = cur.fetchone()[0]
            for ev in result.evidence:
                cur.execute("INSERT INTO diagnostic_evidence (id,run_id,source_kind,source_ref,metric,window_start,window_end,observation,baseline,delta,supports,excerpt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (ev.id,run_id,ev.source_kind,ev.source_ref,ev.metric,ev.window.get('start'),ev.window.get('end'),json.dumps(ev.observation),json.dumps(ev.baseline) if ev.baseline is not None else None,ev.delta,ev.supports,ev.excerpt))
            for h in result.hypotheses:
                cur.execute("INSERT INTO diagnostic_hypotheses (run_id,cause_code,label,confidence,supporting_evidence_ids,contradicting_evidence_ids,missing_data,next_check) VALUES (%s,%s,%s,%s,%s::uuid[],%s::uuid[],%s,%s)", (run_id,h.cause_code,h.label,h.confidence,h.supporting_evidence_ids,h.contradicting_evidence_ids,json.dumps(h.missing_data),h.next_check))
            conn.commit(); return run_id
