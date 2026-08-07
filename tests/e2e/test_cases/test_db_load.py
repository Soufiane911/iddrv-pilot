import subprocess
import os
import pytest
import psycopg2
import redis
import json
import time
from datetime import datetime, timedelta, timezone

pytestmark = [pytest.mark.feature_loader]

def get_data_path(filename):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def run_loader(input_path, db_cli_env, extra_args=None, redis_url=None):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ingest/mapper.py"))
    assert os.path.exists(script_path), f"Loader script {script_path} does not exist"
    args = ["python3", script_path, input_path, "--site-id", "1"]
    if extra_args:
        args.extend(extra_args)
    env = db_cli_env.copy()
    if redis_url:
        env["REDIS_URL"] = redis_url
    return subprocess.run(args, env=env, capture_output=True, text=True)

@pytest.mark.tier1
def test_t1_load_01_basic_bulk_insert(db_url, db_cli_env):
    """
    T1_LOAD_01: Verify bulk insertion of multiple canonical cycle logs.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_bulk.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n")
        start = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(100):
            timestamp = (start + timedelta(seconds=i)).isoformat().replace("+00:00", "Z")
            f.write(f"{timestamp},mach-A,2.5,180.5,12.4\n")
            
    result = run_loader(path, db_cli_env)
    assert result.returncode == 0, f"Loader failed: {result.stderr}"
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        count = cur.fetchone()[0]
        assert count == 100
    conn.close()

@pytest.mark.tier1
def test_t1_load_02_redis_buffer_queueing(db_url, redis_url, db_cli_env):
    """
    T1_LOAD_02: Ensure records are buffered in Redis when buffering is enabled.
    """
    path = get_data_path("load_buffer.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T13:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env, extra_args=["--buffer", "redis"], redis_url=redis_url)
    assert result.returncode == 0
    
    r = redis.Redis.from_url(redis_url)
    queue_len = r.llen("machine_cycles_buffer")
    assert queue_len > 0
    r.close()

@pytest.mark.tier1
def test_t1_load_03_db_insert_conflict_handling(db_url, db_cli_env):
    """
    T1_LOAD_03: Ensure inserting a duplicate record uses ON CONFLICT DO NOTHING or upsert.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_duplicate.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T14:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    res1 = run_loader(path, db_cli_env)
    assert res1.returncode == 0
    
    res2 = run_loader(path, db_cli_env)
    assert res2.returncode == 0, f"Duplicate insert failed: {res2.stderr}"

@pytest.mark.tier1
def test_t1_load_04_transaction_rollback(db_url, db_cli_env):
    """
    T1_LOAD_04: Ensure atomic bulk insertion rolls back fully on database violation.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_rollback.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n")
        f.write("2026-07-09T15:00:00Z,mach-A,2.5,180.5,12.4\n")
        f.write("2026-07-09T15:00:01Z,mach-A,2.5,180.5,12.4\n")
        f.write("2026-07-09T15:00:02Z,non-existent-machine,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env)
    assert result.returncode != 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE time >= '2026-07-09T15:00:00Z';")
        count = cur.fetchone()[0]
        assert count == 0
    conn.close()

@pytest.mark.tier1
def test_t1_load_05_fk_reference_validation(db_url, db_cli_env):
    """
    T1_LOAD_05: Block inserting cycle records referencing a non-existent machine.
    """
    path = get_data_path("load_bad_fk.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T16:00:00Z,ghost-machine,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env)
    assert result.returncode != 0
    assert "foreign key" in result.stderr.lower() or "violates" in result.stderr.lower() or "violation" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_01_db_connection_loss_recovery(db_url, db_cli_env):
    """
    T2_LOAD_01: Ingestion retries and recovers from temporary database disconnects.
    """
    path = get_data_path("load_retry.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T17:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env, extra_args=["--simulate-db-disconnect"])
    assert result.returncode == 0
    assert "retry" in result.stdout.lower() or "retry" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_02_redis_buffer_saturation(db_url, redis_url, db_cli_env):
    """
    T2_LOAD_02: Ingestion pipeline falls back gracefully when Redis memory limit is reached.
    """
    path = get_data_path("load_saturation.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T18:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env, extra_args=["--buffer", "redis", "--simulate-redis-saturation"], redis_url=redis_url)
    assert result.returncode == 0
    assert "local" in result.stdout.lower() or "saturation" in result.stdout.lower() or "pause" in result.stdout.lower() or "saturated" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_03_large_batch_chunking(db_url, db_cli_env):
    """
    T2_LOAD_03: Large batch insertion divided into chunks to avoid parameter limits.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_large.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n")
        start = datetime(2026, 7, 9, 19, 0, 0, tzinfo=timezone.utc)
        for i in range(10000):
            timestamp = (start + timedelta(seconds=i)).isoformat().replace("+00:00", "Z")
            f.write(f"{timestamp},mach-A,2.5,180.5,12.4\n")
            
    result = run_loader(path, db_cli_env)
    assert result.returncode == 0
    assert "chunk" in result.stdout.lower() or "batch" in result.stdout.lower() or "dividing" in result.stdout.lower()

@pytest.mark.tier2
def test_t2_load_04_backfilling_historical_data(db_url, db_cli_env):
    """
    T2_LOAD_04: TimescaleDB hypertable processes backfilled data out of order correctly.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_historical.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-01-09T12:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_cli_env)
    assert result.returncode == 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE time = '2026-01-09T12:00:00Z';")
        count = cur.fetchone()[0]
        assert count == 1
    conn.close()

@pytest.mark.tier2
def test_t2_load_05_null_value_ingestion(db_url, db_cli_env):
    """
    T2_LOAD_05: Ensure missing/null metrics are stored as NULL in database instead of default 0.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name) VALUES ('mach-A', 'Machine A') ON CONFLICT DO NOTHING;")
        cur.execute("DELETE FROM machine_cycles WHERE time = '2026-07-09T20:00:00Z';")
        conn.commit()
    conn.close()
    
    path = get_data_path("load_nulls.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T20:00:00Z,mach-A,2.5,N/A,12.4\n")
        
    result = run_loader(path, db_cli_env)
    assert result.returncode == 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT peak_pressure_bar FROM machine_cycles WHERE time = '2026-07-09T20:00:00Z';")
        val = cur.fetchone()[0]
        assert val is None
    conn.close()


@pytest.mark.tier2
def test_t2_load_06_multi_site_isolation(db_url):
    """
    T2_LOAD_06: Two sites share the same machine reference, alias and
    production order external id.  Imports must be fully isolated — zero
    cross-contamination between sites.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Setup ──────────────────────────────────────────────────────────
    cur.execute("INSERT INTO sites (id, name, timezone) VALUES (2, 'Usine Secondaire', 'Europe/Paris') ON CONFLICT (id) DO NOTHING")
    cur.execute("SELECT setval(pg_get_serial_sequence('sites', 'id'), 2, true)")

    # Same erp_ref on both sites
    for site_id in (1, 2):
        cur.execute(
            "INSERT INTO machines (site_id, erp_ref, name) VALUES (%s, %s, %s) ON CONFLICT (site_id, erp_ref) DO NOTHING",
            (site_id, "MULTI-001", f"Presse Multi-site {site_id}"),
        )
    conn.commit()

    # Fetch machine ids
    cur.execute("SELECT id, site_id FROM machines WHERE erp_ref = 'MULTI-001' ORDER BY site_id")
    machines = {row[1]: row[0] for row in cur.fetchall()}
    assert len(machines) == 2, f"Deux machines attendues, obtenu {len(machines)}"
    m1, m2 = machines[1], machines[2]

    # Same alias_value on both machines (different sites)
    for site_id, mid in machines.items():
        cur.execute(
            "INSERT INTO machine_aliases (machine_id, site_id, alias_context, alias_value) VALUES (%s, %s, 'test', 'PRESSE-ALIAS') ON CONFLICT DO NOTHING",
            (mid, site_id),
        )
    conn.commit()

    # Same external production order id on both sites
    for site_id, mid in machines.items():
        cur.execute(
            "INSERT INTO production_orders (id, site_id, machine_id, product_ref, started_at, ended_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (site_id, id) DO NOTHING",
            ("OF-X-0001", site_id, mid, f"PRODUIT-SITE{site_id}",
             "2026-07-10T08:00:00Z", "2026-07-10T16:00:00Z"),
        )
    conn.commit()

    # ── Insert machine cycles per site ─────────────────────────────────
    for site_id, mid in machines.items():
        ts = "2026-07-10T12:00:00Z"
        cur.execute(
            "INSERT INTO machine_cycles (time, machine_id, production_order_id, order_site_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (ts, mid, "OF-X-0001", site_id),
        )
    conn.commit()

    # ── Assert zero cross-contamination ────────────────────────────────
    # Site 1 cycles must only belong to site 1
    cur.execute(
        "SELECT COUNT(*) FROM machine_cycles mc "
        "JOIN machines m ON m.id = mc.machine_id "
        "WHERE m.site_id = 1"
    )
    site1_cycles = cur.fetchone()[0]
    assert site1_cycles == 1, f"Site 1 doit avoir 1 cycle, obtenu {site1_cycles}"

    # Site 2 cycles must only belong to site 2
    cur.execute(
        "SELECT COUNT(*) FROM machine_cycles mc "
        "JOIN machines m ON m.id = mc.machine_id "
        "WHERE m.site_id = 2"
    )
    site2_cycles = cur.fetchone()[0]
    assert site2_cycles == 1, f"Site 2 doit avoir 1 cycle, obtenu {site2_cycles}"

    # No cycle should reference the wrong site's order
    cur.execute(
        "SELECT COUNT(*) FROM machine_cycles mc "
        "JOIN machines m ON m.id = mc.machine_id "
        "WHERE m.site_id = 1 AND mc.order_site_id = 2"
    )
    cross1 = cur.fetchone()[0]
    assert cross1 == 0, f"Contamination: {cross1} cycles du site 1 pointent vers un OF du site 2"

    cur.execute(
        "SELECT COUNT(*) FROM machine_cycles mc "
        "JOIN machines m ON m.id = mc.machine_id "
        "WHERE m.site_id = 2 AND mc.order_site_id = 1"
    )
    cross2 = cur.fetchone()[0]
    assert cross2 == 0, f"Contamination: {cross2} cycles du site 2 pointent vers un OF du site 1"

    # FK integrity: every order_site_id must match the machine site
    cur.execute(
        "SELECT COUNT(*) FROM machine_cycles mc "
        "JOIN machines m ON m.id = mc.machine_id "
        "WHERE mc.order_site_id IS NOT NULL AND mc.order_site_id != m.site_id"
    )
    mismatch = cur.fetchone()[0]
    assert mismatch == 0, f"Incohérence site: {mismatch} cycles ont order_site_id != machine.site_id"

    # The same binary export is valid once per site, but not twice inside one site.
    shared_hash = "a" * 64
    cur.execute(
        "INSERT INTO import_passports(site_id,file_name,file_hash,status) VALUES (1,'site1.csv',%s,'completed')",
        (shared_hash,),
    )
    cur.execute(
        "INSERT INTO import_passports(site_id,file_name,file_hash,status) VALUES (2,'site2.csv',%s,'completed')",
        (shared_hash,),
    )
    cur.execute("SAVEPOINT duplicate_same_site")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute(
            "INSERT INTO import_passports(site_id,file_name,file_hash,status) VALUES (1,'duplicate.csv',%s,'completed')",
            (shared_hash,),
        )
    cur.execute("ROLLBACK TO SAVEPOINT duplicate_same_site")

    # External context identifiers are also unique per site, not globally.
    for site_id, machine_id in ((1, m1), (2, m2)):
        cur.execute(
            """INSERT INTO quality_checks
                 (site_id,quality_check_id,time,machine_id,production_order_id,order_site_id)
               VALUES (%s,'QC-SHARED','2026-07-10T12:00:00Z',%s,'OF-X-0001',%s)""",
            (site_id, machine_id, site_id),
        )
    cur.execute("SELECT COUNT(*) FROM quality_checks WHERE quality_check_id='QC-SHARED'")
    assert cur.fetchone()[0] == 2
    conn.commit()

    cur.close()
    conn.close()


@pytest.mark.tier2
def test_t2_load_07_comparable_baseline_selection(db_url):
    """The baseline prefers matching product/tool/material over newer unrelated cycles."""
    from backend.app.diagnostics.postgres import PostgresDiagnosticRepository

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO sites(id,name) VALUES (1,'Baseline Site') ON CONFLICT (id) DO NOTHING")
        cur.execute(
            "INSERT INTO machines(site_id,erp_ref,name) VALUES (1,'BASE-1','Baseline machine') RETURNING id"
        )
        machine_id = cur.fetchone()[0]
        orders = [
            ("OF-MATCH", "PRODUCT-A", "MOLD-A", "MAT-A", "2026-07-10T08:00:00Z"),
            ("OF-OTHER", "PRODUCT-B", "MOLD-B", "MAT-B", "2026-07-10T09:00:00Z"),
            ("OF-TARGET", "PRODUCT-A", "MOLD-A", "MAT-A", "2026-07-10T10:00:00Z"),
        ]
        for order_id, product, tool, material, started_at in orders:
            cur.execute(
                """INSERT INTO production_orders
                     (id,site_id,machine_id,product_ref,tool_ref,material_ref,started_at)
                   VALUES (%s,1,%s,%s,%s,%s,%s)""",
                (order_id, machine_id, product, tool, material, started_at),
            )
        for index in range(30):
            cur.execute(
                """INSERT INTO machine_cycles
                     (time,machine_id,production_order_id,order_site_id,scrap_flag)
                   VALUES (%s,%s,'OF-MATCH',1,false)""",
                (datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc) + timedelta(seconds=index), machine_id),
            )
            cur.execute(
                """INSERT INTO machine_cycles
                     (time,machine_id,production_order_id,order_site_id,scrap_flag)
                   VALUES (%s,%s,'OF-OTHER',1,false)""",
                (datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc) + timedelta(seconds=index), machine_id),
            )
        conn.commit()
    conn.close()

    rows = PostgresDiagnosticRepository(db_url).comparable_baseline_cycles(
        machine_id,
        "OF-TARGET",
        datetime(2026, 7, 10, 10, 0, tzinfo=timezone.utc),
        30,
    )
    assert len(rows) == 30
    assert {row["production_order_id"] for row in rows} == {"OF-MATCH"}


@pytest.mark.tier2
def test_t2_load_08_runtime_detector_is_idempotent(db_url, monkeypatch):
    """A committed cycle passport creates one incident, never duplicates it."""
    from types import SimpleNamespace
    from backend.app.diagnostics.runtime import trigger_after_import
    import backend.app.db as db_module
    from backend.app.config import Settings

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO sites(id,name) VALUES (1,'Detector Site') ON CONFLICT (id) DO NOTHING")
        cur.execute(
            "INSERT INTO machines(site_id,erp_ref,name) VALUES (1,'DET-1','Detector machine') RETURNING id"
        )
        machine_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO production_orders(id,site_id,machine_id,started_at)
               VALUES ('OF-DETECT',1,%s,'2026-07-10T08:00:00Z')""",
            (machine_id,),
        )
        passport_ids = []
        for suffix in (1, 2):
            cur.execute(
                """INSERT INTO import_passports(site_id,file_name,file_hash,status)
                   VALUES (1,%s,%s,'completed') RETURNING id""",
                (f"detect-{machine_id}-{suffix}.csv", f"{machine_id * 10 + suffix:064x}"[-64:]),
            )
            passport_ids.append(cur.fetchone()[0])
        baseline_passport_id, incident_passport_id = passport_ids
        start = datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)
        for index in range(60):
            scrap = index >= 30 and index < 52
            passport_id = baseline_passport_id if index < 30 else incident_passport_id
            cur.execute(
                """INSERT INTO machine_cycles
                     (time,machine_id,production_order_id,order_site_id,passport_id,
                      scrap_flag,part_quality_status,defect_type)
                   VALUES (%s,%s,'OF-DETECT',1,%s,%s,%s,%s)""",
                (
                    start + timedelta(seconds=index), machine_id, passport_id, scrap,
                    "scrap" if scrap else "good", "short_shot" if scrap else None,
                ),
            )
        conn.commit()
    conn.close()

    monkeypatch.setattr(db_module, "settings", Settings(database_url=db_url))
    job = SimpleNamespace(site_id=1, passport_id=str(incident_passport_id))
    result = {
        "transaction_committed": True,
        "site_id": 1,
        "passport_id": str(incident_passport_id),
    }
    first = trigger_after_import(job, result)
    second = trigger_after_import(job, result)
    assert first == {"detected": 1, "inserted": 1}
    assert second == {"detected": 1, "inserted": 0}

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM incidents WHERE machine_id=%s", (machine_id,))
        assert cur.fetchone()[0] == 1
    conn.close()
