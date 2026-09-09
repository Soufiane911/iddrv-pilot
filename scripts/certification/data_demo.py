"""Synthetic CSV/JSON -> temporary SQLite projection -> API Site payload.

No network, environment credentials, production DB or industrial extraction.
The projection follows db/init.sql sites/machines, not its PostgreSQL DDL.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile

SITES = '[{"id":1,"name":"Synthetic A","timezone":"UTC"},{"id":2,"name":"Synthetic B","timezone":"UTC"}]'
MACHINES = "id,site_id,erp_ref,name\n1,1, SYN-01 ,Synthetic one\n2,1,SYN-02,Synthetic two\n3,2,SYN-03,Synthetic other site\n4,1,,Rejected missing reference\n1,1,SYN-01,Synthetic one\n"
DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE sites(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, timezone TEXT NOT NULL);
CREATE TABLE machines(id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id),
 erp_ref TEXT NOT NULL, name TEXT, UNIQUE(site_id, erp_ref));
CREATE INDEX machines_site ON machines(site_id);
"""
QUERY = """SELECT s.id, s.name, s.timezone, COUNT(m.id) AS machine_count
FROM sites s LEFT JOIN machines m ON m.site_id=s.id
WHERE s.id=? GROUP BY s.id, s.name, s.timezone ORDER BY s.id"""


def run_demo(machine_csv=MACHINES, site_id=1):
    """Return deterministic evidence; DB deleted automatically even on failure."""
    rejected, seen, rows = [], set(), []
    for number, row in enumerate(csv.DictReader(io.StringIO(machine_csv)), 2):
        try:
            record = (int(row['id']), int(row['site_id']), row['erp_ref'].strip(), row['name'].strip())
            if not record[2] or min(record[:2]) < 1:
                raise ValueError('required')
        except (ValueError, KeyError, AttributeError, TypeError):
            rejected.append({'line': number, 'reason': 'invalid_record'})
            continue
        if record in seen:
            rejected.append({'line': number, 'reason': 'exact_duplicate'})
            continue
        seen.add(record)
        rows.append(record)
    with tempfile.TemporaryDirectory(prefix='iddrv-certification-') as directory:
        with sqlite3.connect(Path(directory) / 'synthetic.sqlite') as db:
            db.row_factory = sqlite3.Row
            db.executescript(DDL)
            with db:
                db.executemany('INSERT INTO sites VALUES (:id,:name,:timezone)', json.loads(SITES))
                db.executemany('INSERT INTO machines VALUES (?,?,?,?)', rows)
            payload = [dict(row) for row in db.execute(QUERY, (site_id,))]
            imported = db.execute('SELECT COUNT(*) FROM machines').fetchone()[0]
            plan = [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + QUERY, (site_id,))]
        db.close()
    return {'synthetic': True, 'engine': 'sqlite_projection_not_postgresql',
            'sources_sha256': {'sites_json': hashlib.sha256(SITES.encode()).hexdigest(),
                               'machines_csv': hashlib.sha256(machine_csv.encode()).hexdigest()},
            'input_rows': len(list(csv.DictReader(io.StringIO(machine_csv)))),
            'imported_rows': imported, 'rejections': rejected, 'site_payload': payload,
            'query_plan': plan}


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2, ensure_ascii=False))
