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

def run_loader(input_path, db_url, extra_args=None):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ingest/mapper.py"))
    assert os.path.exists(script_path), f"Loader script {script_path} does not exist"
    args = ["python3", script_path, input_path, "--db-url", db_url]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    return result

@pytest.mark.tier1
def test_t1_load_01_basic_bulk_insert(db_url):
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
            
    result = run_loader(path, db_url)
    assert result.returncode == 0, f"Loader failed: {result.stderr}"
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        count = cur.fetchone()[0]
        assert count == 100
    conn.close()

@pytest.mark.tier1
def test_t1_load_02_redis_buffer_queueing(db_url, redis_url):
    """
    T1_LOAD_02: Ensure records are buffered in Redis when buffering is enabled.
    """
    path = get_data_path("load_buffer.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T13:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_url, extra_args=["--buffer", "redis", "--redis-url", redis_url])
    assert result.returncode == 0
    
    r = redis.Redis.from_url(redis_url)
    queue_len = r.llen("machine_cycles_buffer")
    assert queue_len > 0
    r.close()

@pytest.mark.tier1
def test_t1_load_03_db_insert_conflict_handling(db_url):
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
        
    res1 = run_loader(path, db_url)
    assert res1.returncode == 0
    
    res2 = run_loader(path, db_url)
    assert res2.returncode == 0, f"Duplicate insert failed: {res2.stderr}"

@pytest.mark.tier1
def test_t1_load_04_transaction_rollback(db_url):
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
        
    result = run_loader(path, db_url)
    assert result.returncode != 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE time >= '2026-07-09T15:00:00Z';")
        count = cur.fetchone()[0]
        assert count == 0
    conn.close()

@pytest.mark.tier1
def test_t1_load_05_fk_reference_validation(db_url):
    """
    T1_LOAD_05: Block inserting cycle records referencing a non-existent machine.
    """
    path = get_data_path("load_bad_fk.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T16:00:00Z,ghost-machine,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_url)
    assert result.returncode != 0
    assert "foreign key" in result.stderr.lower() or "violates" in result.stderr.lower() or "violation" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_01_db_connection_loss_recovery(db_url):
    """
    T2_LOAD_01: Ingestion retries and recovers from temporary database disconnects.
    """
    path = get_data_path("load_retry.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T17:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_url, extra_args=["--simulate-db-disconnect"])
    assert result.returncode == 0
    assert "retry" in result.stdout.lower() or "retry" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_02_redis_buffer_saturation(db_url, redis_url):
    """
    T2_LOAD_02: Ingestion pipeline falls back gracefully when Redis memory limit is reached.
    """
    path = get_data_path("load_saturation.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T18:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_loader(path, db_url, extra_args=["--buffer", "redis", "--redis-url", redis_url, "--simulate-redis-saturation"])
    assert result.returncode == 0
    assert "local" in result.stdout.lower() or "saturation" in result.stdout.lower() or "pause" in result.stdout.lower() or "saturated" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_load_03_large_batch_chunking(db_url):
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
            
    result = run_loader(path, db_url)
    assert result.returncode == 0
    assert "chunk" in result.stdout.lower() or "batch" in result.stdout.lower() or "dividing" in result.stdout.lower()

@pytest.mark.tier2
def test_t2_load_04_backfilling_historical_data(db_url):
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
        
    result = run_loader(path, db_url)
    assert result.returncode == 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machine_cycles WHERE time = '2026-01-09T12:00:00Z';")
        count = cur.fetchone()[0]
        assert count == 1
    conn.close()

@pytest.mark.tier2
def test_t2_load_05_null_value_ingestion(db_url):
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
        
    result = run_loader(path, db_url)
    assert result.returncode == 0
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT peak_pressure_bar FROM machine_cycles WHERE time = '2026-07-09T20:00:00Z';")
        val = cur.fetchone()[0]
        assert val is None
    conn.close()
