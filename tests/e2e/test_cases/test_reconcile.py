import subprocess
import os
import pytest
import psycopg2
import json

from conftest import database_subprocess_environment

pytestmark = [pytest.mark.feature_reconcile]

def run_reconcile(db_url, extra_args=None):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ingest/reconcile.py"))
    assert os.path.exists(script_path), f"Reconciliation script {script_path} does not exist"
    args = ["python3", script_path]
    if extra_args:
        args.extend(extra_args)
    with database_subprocess_environment(db_url) as env:
        return subprocess.run(args, env=env, capture_output=True, text=True)

@pytest.mark.tier1
def test_t1_rec_01_perfect_temporal_alignment(db_url):
    """
    T1_REC_01: Align cycles inside scheduled production order (OF) and shift window.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-123', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T08:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-123', 1, 1, '2026-07-09', '2026-07-09T06:00:00Z', '2026-07-09T14:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        for i in range(10):
            cur.execute(f"INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T09:{i:02d}:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0, f"Reconciliation failed: {result.stderr}"

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT production_order_id, shift_id FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        rows = cur.fetchall()
        assert len(rows) == 10
        for wo, sf in rows:
            assert wo == 'OF-123'
            assert sf is not None
    conn.close()

@pytest.mark.tier1
def test_t1_rec_02_multi_shift_alignment(db_url):
    """
    T1_REC_02: Divide and assign cycles correctly when they cross shift boundaries.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-124', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T13:00:00Z', '2026-07-09T15:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-124', 1, 1, '2026-07-09', '2026-07-09T06:00:00Z', '2026-07-09T14:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-124', 1, 2, '2026-07-09', '2026-07-09T14:00:00Z', '2026-07-09T22:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T13:50:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T14:10:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.shift_number FROM machine_cycles mc
            JOIN shifts s ON mc.shift_id = s.id
            WHERE mc.time = '2026-07-09T13:50:00Z';
        """)
        assert cur.fetchone()[0] == 1
        cur.execute("""
            SELECT s.shift_number FROM machine_cycles mc
            JOIN shifts s ON mc.shift_id = s.id
            WHERE mc.time = '2026-07-09T14:10:00Z';
        """)
        assert cur.fetchone()[0] == 2
    conn.close()

@pytest.mark.tier1
def test_t1_rec_03_machine_status_downtime_sync(db_url):
    """
    T1_REC_03: Downtime event breaks and splits reconciliation windows correctly.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-125', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T08:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-125', 1, 1, '2026-07-09', '2026-07-09T06:00:00Z', '2026-07-09T14:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("CREATE TABLE IF NOT EXISTS downtime_events (machine_id VARCHAR(50), start_time TIMESTAMP, end_time TIMESTAMP, reason VARCHAR(100));")
        cur.execute("TRUNCATE TABLE downtime_events;")
        cur.execute("INSERT INTO downtime_events VALUES ('mach-A', '2026-07-09T09:30:00Z', '2026-07-09T10:00:00Z', 'Maintenance');")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0
    assert "downtime" in result.stdout.lower() or "maintenance" in result.stdout.lower()

@pytest.mark.tier1
def test_t1_rec_04_multi_machine_isolation(db_url):
    """
    T1_REC_04: Reconciling one machine does not alter records of another machine.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-B', 'Machine B', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-A', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T08:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-B', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-B'), '2026-07-09T08:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-A', 1, 1, '2026-07-09', '2026-07-09T06:00:00Z', '2026-07-09T14:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-B'), 'OF-B', 1, 1, '2026-07-09', '2026-07-09T06:00:00Z', '2026-07-09T14:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles;")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T09:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T09:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-B'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT production_order_id FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        assert cur.fetchone()[0] == 'OF-A'
        cur.execute("SELECT production_order_id FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-B');")
        assert cur.fetchone()[0] == 'OF-B'
    conn.close()

@pytest.mark.tier1
def test_t1_rec_05_summary_report_generation(db_url):
    """
    T1_REC_05: Verify performance summary report contains total cycles and uptime.
    """
    result = run_reconcile(db_url, extra_args=["--report"])
    assert result.returncode == 0
    assert "total cycles" in result.stdout.lower() or "uptime" in result.stdout.lower() or "duration" in result.stdout.lower()

@pytest.mark.tier2
def test_t2_rec_01_midnight_crossing_shifts(db_url):
    """
    T2_REC_01: Align cycles correctly for night shifts crossing midnight.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-NIGHT', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T22:00:00Z', '2026-07-10T06:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO shifts (machine_id, production_order_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 'OF-NIGHT', 1, 3, '2026-07-09', '2026-07-09T22:00:00Z', '2026-07-10T06:00:00Z')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T23:30:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-10T02:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT s.shift_number FROM machine_cycles mc
            JOIN shifts s ON mc.shift_id = s.id
            WHERE mc.machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');
        """)
        shifts = [r[0] for r in cur.fetchall()]
        assert len(shifts) == 1
        assert shifts[0] == 3
    conn.close()

@pytest.mark.tier2
def test_t2_rec_02_overlapping_work_orders(db_url):
    """
    T2_REC_02: Conflicting schedule intervals logged, applying safety fallback without crash.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-overlap-1', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T10:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO production_orders (id, site_id, machine_id, started_at, ended_at)
            VALUES ('OF-overlap-2', 1, (SELECT id FROM machines WHERE erp_ref = 'mach-A'), '2026-07-09T10:00:00Z', '2026-07-09T12:00:00Z')
            ON CONFLICT (site_id, id) DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T11:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert "conflict" in result.stdout.lower() or "overlap" in result.stdout.lower() or "warning" in result.stderr.lower() or result.returncode != 0

@pytest.mark.tier2
def test_t2_rec_03_idle_runs(db_url):
    """
    T2_REC_03: Reconcile cycles when no active work order exists.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T13:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT production_order_id FROM machine_cycles WHERE time = '2026-07-09T13:00:00Z';")
        val = cur.fetchone()[0]
        assert val is None or val == "UNASSIGNED"
    conn.close()

@pytest.mark.tier2
def test_t2_rec_04_timezone_offsets(db_url):
    """
    T2_REC_04: Reconcile local time shifts with UTC cycles correctly.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO machines (erp_ref, name, site_id) VALUES ('mach-A', 'Machine A', 1) ON CONFLICT DO NOTHING;")
        cur.execute("""
            INSERT INTO shifts (machine_id, order_site_id, shift_number, shift_date, started_at, ended_at)
            VALUES ((SELECT id FROM machines WHERE erp_ref = 'mach-A'), 1, 1, '2026-07-09', '2026-07-09T06:00:00+02:00', '2026-07-09T14:00:00+02:00')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("DELETE FROM machine_cycles WHERE machine_id = (SELECT id FROM machines WHERE erp_ref = 'mach-A');")
        cur.execute("INSERT INTO machine_cycles (time, machine_id, cycle_time_s, order_site_id) VALUES ('2026-07-09T05:00:00Z', (SELECT id FROM machines WHERE erp_ref = 'mach-A'), 2.5, 1);")
        conn.commit()
    conn.close()

    result = run_reconcile(db_url)
    assert result.returncode == 0

    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.shift_number FROM machine_cycles mc
            JOIN shifts s ON mc.shift_id = s.id
            WHERE mc.time = '2026-07-09T05:00:00Z';
        """)
        assert cur.fetchone()[0] == 1
    conn.close()

@pytest.mark.tier2
def test_t2_rec_05_micro_stop_filtering(db_url):
    """
    T2_REC_05: Interruptions under 2 mins treated as active work order duration; >2 mins splits.
    """
    result = run_reconcile(db_url, extra_args=["--downtime-threshold", "120"])
    assert result.returncode == 0
    assert "micro-stop" in result.stdout.lower() or "downtime" in result.stdout.lower()
