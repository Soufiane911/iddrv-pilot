import pytest
import psycopg2
import redis

def pytest_configure(config):
    # Register custom markers to avoid warnings
    config.addinivalue_line("markers", "tier1: Run tier 1 (Happy Path) E2E tests")
    config.addinivalue_line("markers", "tier2: Run tier 2 (Boundary & Error) E2E tests")
    config.addinivalue_line("markers", "tier3: Run tier 3 integration/workload E2E tests")
    config.addinivalue_line("markers", "tier4: Run tier 4 integration/workload E2E tests")
    config.addinivalue_line("markers", "feature_schema: E2E tests for schema initialization")
    config.addinivalue_line("markers", "feature_profiler: E2E tests for format profiling")
    config.addinivalue_line("markers", "feature_mapper: E2E tests for canonical mapping")
    config.addinivalue_line("markers", "feature_loader: E2E tests for DB loading")
    config.addinivalue_line("markers", "feature_reconcile: E2E tests for temporal reconciliation")

def pytest_addoption(parser):
    parser.addoption("--tier", action="store", default="1,2", help="Tiers of tests to run (comma-separated, e.g., '1' or '1,2')")
    parser.addoption("--feature", action="store", default="all", help="Features to run (comma-separated, e.g., 'schema,profiler' or 'all')")
    parser.addoption("--db-url", action="store", default="postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv_test", help="Database connection URL")
    parser.addoption("--redis-url", action="store", default="redis://localhost:6379/1", help="Redis connection URL")

def pytest_collection_modifyitems(config, items):
    tier_option = config.getoption("--tier")
    feature_option = config.getoption("--feature")
    
    # Parse tiers
    requested_tiers = []
    if tier_option:
        requested_tiers = [t.strip() for t in str(tier_option).split(",")]
        
    # Parse features
    requested_features = []
    if feature_option and feature_option != "all":
        requested_features = [f.strip() for f in str(feature_option).split(",")]
        
    keep = []
    for item in items:
        # Determine item tier
        item_tier = None
        for mark in item.iter_markers():
            if mark.name in ["tier1", "tier2", "tier3", "tier4"]:
                item_tier = mark.name.replace("tier", "")
                break
                
        # Determine item feature
        item_feature = None
        for mark in item.iter_markers():
            if mark.name.startswith("feature_"):
                item_feature = mark.name.replace("feature_", "")
                break
                
        # Match tier
        tier_match = True
        if requested_tiers and item_tier:
            tier_match = item_tier in requested_tiers
            
        # Match feature
        feature_match = True
        if requested_features and item_feature:
            feature_match = item_feature in requested_features
            
        if tier_match and feature_match:
            keep.append(item)
            
    items[:] = keep

@pytest.fixture(scope="session")
def db_url(request):
    return request.config.getoption("--db-url")

@pytest.fixture(scope="session")
def redis_url(request):
    return request.config.getoption("--redis-url")

@pytest.fixture(scope="session")
def db_conn(db_url):
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        yield conn
        conn.close()
    except Exception:
        yield None

@pytest.fixture(scope="session")
def redis_conn(redis_url):
    try:
        r = redis.Redis.from_url(redis_url)
        yield r
        r.close()
    except Exception:
        yield None

@pytest.fixture(autouse=True)
def clean_db(db_conn):
    """
    Clean the dedicated test database before and after each test case.

    Tests create their own PostgreSQL connections. When a failing assertion
    leaves one of these transactions open, it can keep a lock that would make
    the following TRUNCATE block forever. Terminate only the other sessions on
    the current test database, then fail fast if cleanup itself cannot run.
    """
    def _truncate_all():
        if db_conn is None:
            raise RuntimeError("Connexion a la base E2E indisponible")

        with db_conn.cursor() as cur:
            cur.execute("SET lock_timeout = '5s'")
            cur.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
            """)
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                  AND table_name NOT IN ('spatial_ref_sys')
            """)
            tables = [r[0] for r in cur.fetchall()]
            if tables:
                quoted_tables = [f'"{t}"' for t in tables]
                cur.execute(f"TRUNCATE TABLE {', '.join(quoted_tables)} CASCADE;")
            if "sites" in tables:
                cur.execute("""
                    INSERT INTO sites (id, name, timezone)
                    VALUES (1, 'E2E Test Site', 'UTC')
                    ON CONFLICT (id) DO NOTHING
                """)
                cur.execute("SELECT setval(pg_get_serial_sequence('sites', 'id'), 1, true)")
                
    _truncate_all()
    yield
    _truncate_all()

@pytest.fixture(autouse=True)
def clean_redis(redis_conn):
    """
    Flush the Redis DB before and after each test case.
    Handles missing connections gracefully.
    """
    def _flush_all():
        if redis_conn is not None:
            try:
                redis_conn.flushdb()
            except Exception:
                pass
                
    _flush_all()
    yield
    _flush_all()
