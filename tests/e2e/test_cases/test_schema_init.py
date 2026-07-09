import subprocess
import os
import pytest
import psycopg2

# Marks for tiers and features
pytestmark = [pytest.mark.feature_schema]

@pytest.mark.tier1
def test_t1_init_01_fresh_schema_creation(db_url):
    """
    T1_INIT_01: Ensure setup_db.py initializes the schema, creating required tables.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    # Run the setup script as a subprocess
    result = subprocess.run(["python3", script_path, "--db-url", db_url], capture_output=True, text=True)
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    
    # Verify tables exist via connection
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('machines', 'production_orders', 'shifts', 'machine_cycles');
        """)
        tables = [r[0] for r in cur.fetchall()]
        assert "machines" in tables
        assert "production_orders" in tables
        assert "shifts" in tables
        assert "machine_cycles" in tables
    conn.close()

@pytest.mark.tier1
def test_t1_init_02_timescaledb_extension(db_url):
    """
    T1_INIT_02: Ensure timescaledb extension is enabled in the database.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb';")
        res = cur.fetchone()
        assert res is not None, "timescaledb extension is not installed"
        assert res[0] == "timescaledb"
    conn.close()

@pytest.mark.tier1
def test_t1_init_03_machine_cycles_hypertable(db_url):
    """
    T1_INIT_03: Confirm the machine_cycles table is structured as a TimescaleDB hypertable.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM _timescaledb_catalog.hypertable WHERE table_name = 'machine_cycles';")
        res = cur.fetchone()
        assert res is not None, "machine_cycles is not a TimescaleDB hypertable"
    conn.close()

@pytest.mark.tier1
def test_t1_init_04_metadata_schema_structure(db_url):
    """
    T1_INIT_04: Check that key relational columns are properly typed and exist.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        # Check machines primary key
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns 
            WHERE table_name = 'machines' AND column_name = 'id';
        """)
        res = cur.fetchone()
        assert res is not None, "machines.id column not found"
        
        # Check production_orders primary key
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns 
            WHERE table_name = 'production_orders' AND column_name = 'id';
        """)
        res = cur.fetchone()
        assert res is not None, "production_orders.id column not found"
    conn.close()

@pytest.mark.tier1
def test_t1_init_05_reference_data_seeding(db_url):
    """
    T1_INIT_05: Confirm seed option inserts reference machines and aliases.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    result = subprocess.run(["python3", script_path, "--db-url", db_url, "--seed"], capture_output=True, text=True)
    assert result.returncode == 0, f"Seeding failed: {result.stderr}"
    
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM machines;")
        machine_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM machine_aliases;")
        alias_count = cur.fetchone()[0]
        assert machine_count > 0, "No seed machines found"
        assert alias_count > 0, "No seed machine aliases found"
    conn.close()

@pytest.mark.tier2
def test_t2_init_01_reinitialization_idempotency(db_url):
    """
    T2_INIT_01: Ensure running setup_db.py twice does not cause errors or duplicate constraints.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    # Run once
    result1 = subprocess.run(["python3", script_path, "--db-url", db_url], capture_output=True, text=True)
    assert result1.returncode == 0, f"First run failed: {result1.stderr}"
    
    # Run twice
    result2 = subprocess.run(["python3", script_path, "--db-url", db_url], capture_output=True, text=True)
    assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

@pytest.mark.tier2
def test_t2_init_02_setup_missing_timescaledb(db_url):
    """
    T2_INIT_02: Setup behaves gracefully if run against database without TimescaleDB capability.
    """
    # Note: We can simulate this by running setup with an option or mocking pg_extension check,
    # or by running on a database system where timescaledb is blocked.
    # For a general E2E test, if we cannot simulate a missing extension, we can check if
    # the script has appropriate error exit codes when TimescaleDB fails to create.
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    # Let's run a test targeting a hypothetical non-timescale db if we can, 
    # or assert the script outputs extension validation error when extension fails to load.
    # In opaque-box E2E tests, we run the script with a special flag if implemented,
    # or we verify that when setup_db.py encounters a failure to CREATE EXTENSION, it exits cleanly.
    # Here, we expect the setup script to handle missing timescaledb extension cleanly.
    # We will trigger the command and assert it has a robust check.
    result = subprocess.run(["python3", script_path, "--db-url", db_url, "--simulate-no-timescale"], capture_output=True, text=True)
    # The script should exit with a non-zero code if it detects timescale is unavailable
    assert result.returncode != 0
    assert "timescaledb" in result.stderr.lower() or "timescaledb" in result.stdout.lower()

@pytest.mark.tier2
def test_t2_init_03_db_credential_failure(db_url):
    """
    T2_INIT_03: DB credentials/host failure results in clean error message and non-zero exit code.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    bad_url = "postgresql://invalid_user:invalid_pass@localhost:9999/invalid_db"
    result = subprocess.run(["python3", script_path, "--db-url", bad_url], capture_output=True, text=True)
    assert result.returncode != 0
    # Error should be descriptive and not a raw, unhandled python Traceback in stderr
    assert "traceback" not in result.stderr.lower()
    assert "connect" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_init_04_version_mismatch_handling(db_url):
    """
    T2_INIT_04: Prevent running older setup version against a newer database schema version.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    # Setup the DB first
    subprocess.run(["python3", script_path, "--db-url", db_url], capture_output=True)
    
    # Manually insert a newer version string in a metadata table (if version tracking is implemented)
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        # Create metadata table if not exists and insert v2.0.0
        cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version VARCHAR(50));")
        cur.execute("TRUNCATE TABLE schema_version;")
        cur.execute("INSERT INTO schema_version VALUES ('v2.0.0');")
        conn.commit()
    conn.close()
    
    # Run setup script (which is v1.0.0)
    result = subprocess.run(["python3", script_path, "--db-url", db_url], capture_output=True, text=True)
    assert result.returncode != 0
    assert "version" in result.stderr.lower() or "version" in result.stdout.lower()

@pytest.mark.tier2
def test_t2_init_05_concurrent_init_locking(db_url):
    """
    T2_INIT_05: Concurrent initialization attempts should not corrupt the database.
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../db/setup_db.py"))
    assert os.path.exists(script_path), f"Setup script {script_path} does not exist"
    
    # Spawn two parallel initialization commands
    p1 = subprocess.Popen(["python3", script_path, "--db-url", db_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen(["python3", script_path, "--db-url", db_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    out1, err1 = p1.communicate()
    out2, err2 = p2.communicate()
    
    # At least one must succeed; the other can either succeed (if concurrent locks resolve)
    # or exit cleanly with a concurrency warning/lock error. None should crash.
    codes = [p1.returncode, p2.returncode]
    assert 0 in codes
