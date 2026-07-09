"""Read/write boundary for the G2 investigation API."""
from datetime import datetime
from uuid import UUID
from .db import get_connection

def _incident(row):
    keys = ("id","site_id","machine_id","machine_erp_ref","production_order_id","status","severity","symptom","defect_type","started_at","ended_at","created_at","data_cutoff","confidence")
    return dict(zip(keys, row))

def list_incidents(site_id=None, start=None, end=None, status=None):
    clauses, args = [], []
    if site_id is not None: clauses.append("i.site_id=%s"); args.append(site_id)
    if start is not None: clauses.append("i.started_at >= %s"); args.append(start)
    if end is not None: clauses.append("i.started_at <= %s"); args.append(end)
    if status is not None: clauses.append("i.status=%s"); args.append(status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = """SELECT i.id,i.site_id,i.machine_id,m.erp_ref,i.production_order_id,i.status,i.severity,i.symptom,i.defect_type,i.started_at,i.ended_at,i.created_at,i.data_cutoff,i.confidence FROM incidents i LEFT JOIN machines m ON m.id=i.machine_id""" + where + " ORDER BY i.started_at DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args); return [_incident(r) for r in cur.fetchall()]

def get_incident(incident_id: UUID):
    rows = list_incidents()
    return next((r for r in rows if str(r["id"]) == str(incident_id)), None)

def get_evidence(incident_id: UUID):
    sql = """SELECT e.id,e.source_kind,e.source_ref,e.metric,e.window_start,e.window_end,e.observation,e.baseline,e.delta,e.supports,e.excerpt FROM diagnostic_evidence e JOIN diagnostic_runs r ON r.id=e.run_id WHERE r.incident_id=%s ORDER BY e.window_start"""
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

def persist_investigation(incident_id, result, as_of):
    """Persist engine output and return its run id (JSONB values are adapted by psycopg)."""
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO diagnostic_runs (incident_id,engine,status,completed_at,data_cutoff,result) VALUES (%s,'deterministic_local','completed',NOW(),%s,%s) RETURNING id", (str(incident_id), as_of, json.dumps(result.to_dict())))
            run_id = cur.fetchone()[0]
            for ev in result.evidence:
                cur.execute("INSERT INTO diagnostic_evidence (id,run_id,source_kind,source_ref,metric,window_start,window_end,observation,baseline,delta,supports,excerpt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (ev.id,run_id,ev.source_kind,ev.source_ref,ev.metric,ev.window.get('start'),ev.window.get('end'),json.dumps(ev.observation),json.dumps(ev.baseline) if ev.baseline is not None else None,ev.delta,ev.supports,ev.excerpt))
            for h in result.hypotheses:
                cur.execute("INSERT INTO diagnostic_hypotheses (run_id,cause_code,label,confidence,supporting_evidence_ids,contradicting_evidence_ids,missing_data,next_check) VALUES (%s,%s,%s,%s,%s::uuid[],%s::uuid[],%s,%s) ON CONFLICT DO NOTHING", (run_id,h.cause_code,h.label,h.confidence,h.supporting_evidence_ids,h.contradicting_evidence_ids,json.dumps(h.missing_data),h.next_check))
            conn.commit(); return run_id
