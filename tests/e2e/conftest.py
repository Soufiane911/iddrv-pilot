import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

import pytest
import psycopg2
import redis


def _local_setting(name: str, default: str = "") -> str:
    if value := os.getenv(name):
        return value
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1]
    return default


def _default_db_url() -> str:
    if explicit := os.getenv("E2E_DATABASE_URL"):
        return explicit
    user = _local_setting("POSTGRES_USER", "iddrv_user")
    password = quote(_local_setting("POSTGRES_PASSWORD"), safe="")
    credentials = f"{user}:{password}" if password else user
    return f"postgresql://{credentials}@localhost:5432/iddrv_test"


_E2E_DATABASE = "iddrv_test"
_E2E_GUARD_TABLE = "_iddrv_e2e_guard"
_E2E_GUARD_TOKEN = "iddrv-e2e-owned-v1"
_E2E_REDIS_GUARD_KEY = "iddrv:e2e:ownership-guard"
_E2E_CONFIRMATION = "iddrv_test:truncate-and-redis-1:flush"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _cleanup_is_confirmed() -> bool:
    return _local_setting("E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION") == _E2E_CONFIRMATION


def _validate_test_database(url: str) -> None:
    parsed = urlparse(url)
    database = unquote(parsed.path.lstrip("/"))
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname not in _LOCAL_HOSTS:
        raise pytest.UsageError("La suite E2E exige une base PostgreSQL locale dédiée.")
    if parsed.params or parsed.query or parsed.fragment:
        raise pytest.UsageError("Les paramètres de routage sont interdits dans l’URL PostgreSQL E2E.")
    if database != _E2E_DATABASE:
        raise pytest.UsageError(f"La suite E2E accepte uniquement la base dédiée '{_E2E_DATABASE}'.")
    if not _cleanup_is_confirmed():
        raise pytest.UsageError("Définissez E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION avec la valeur documentée avant tout nettoyage E2E.")


def _validate_test_redis(url: str) -> None:
    parsed = urlparse(url)
    database = unquote(parsed.path.lstrip("/"))
    if parsed.scheme != "redis" or parsed.hostname not in _LOCAL_HOSTS or database != "1":
        raise pytest.UsageError("La suite E2E exige la base Redis locale dédiée numéro 1.")
    if parsed.params or parsed.query or parsed.fragment:
        raise pytest.UsageError("Les paramètres de routage sont interdits dans l’URL Redis E2E.")
    if not _cleanup_is_confirmed():
        raise pytest.UsageError("Le nettoyage Redis E2E exige une confirmation destructive explicite.")


def _assert_effective_database_target(conn) -> None:
    dsn = conn.get_dsn_parameters()
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
        cursor.execute(f"SELECT token FROM {_E2E_GUARD_TABLE} WHERE token = %s", (_E2E_GUARD_TOKEN,))
        guard = cursor.fetchone()
    if database != _E2E_DATABASE or dsn.get("host") not in _LOCAL_HOSTS or guard is None:
        raise pytest.UsageError("La cible PostgreSQL effective ne porte pas la sentinelle E2E attendue.")


def initialize_e2e_guard(url: str) -> None:
    _validate_test_database(url)
    conn = psycopg2.connect(url)
    try:
        dsn = conn.get_dsn_parameters()
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
            if database != _E2E_DATABASE or dsn.get("host") not in _LOCAL_HOSTS:
                raise pytest.UsageError("Refus d’initialiser la sentinelle sur une cible PostgreSQL inattendue.")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {_E2E_GUARD_TABLE} (token TEXT PRIMARY KEY)")
            cursor.execute(
                f"INSERT INTO {_E2E_GUARD_TABLE} (token) VALUES (%s) ON CONFLICT DO NOTHING",
                (_E2E_GUARD_TOKEN,),
            )
        conn.commit()
    finally:
        conn.close()


def initialize_e2e_redis_guard(url: str) -> None:
    _validate_test_redis(url)
    client = redis.Redis.from_url(url)
    try:
        settings = client.connection_pool.connection_kwargs
        if settings.get("host") not in _LOCAL_HOSTS or int(settings.get("db", -1)) != 1:
            raise pytest.UsageError("Refus d’initialiser la sentinelle sur une cible Redis inattendue.")
        client.set(_E2E_REDIS_GUARD_KEY, _E2E_GUARD_TOKEN)
    finally:
        client.close()


def _passwordless_database_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    hostname = parsed.hostname or ""
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port:
        rendered_host = f"{rendered_host}:{parsed.port}"
    userinfo = f"{quote(username, safe='')}@" if username else ""
    safe_url = urlunparse(parsed._replace(netloc=f"{userinfo}{rendered_host}"))
    return safe_url, password


def _pgpass_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:")


@contextmanager
def database_subprocess_environment(url: str):
    _validate_test_database(url)
    safe_url, password = _passwordless_database_url(url)
    env = os.environ.copy()
    env["DATABASE_URL"] = safe_url
    passfile = None
    try:
        if password:
            parsed = urlparse(url)
            handle = tempfile.NamedTemporaryFile(mode="w", prefix="iddrv-e2e-pgpass-", delete=False)
            passfile = Path(handle.name)
            handle.write(":".join([
                _pgpass_escape(parsed.hostname or ""),
                str(parsed.port or 5432),
                "*",
                _pgpass_escape(unquote(parsed.username or "")),
                _pgpass_escape(password),
            ]) + "\n")
            handle.close()
            passfile.chmod(0o600)
            env["PGPASSFILE"] = str(passfile)
        yield env
    finally:
        if passfile is not None:
            passfile.unlink(missing_ok=True)

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
    parser.addoption("--db-url", action="store", default=_default_db_url(), help="Database connection URL")
    parser.addoption("--redis-url", action="store", default=os.getenv("E2E_REDIS_URL", "redis://localhost:6379/1"), help="Redis connection URL")

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
    value = request.config.getoption("--db-url")
    _validate_test_database(value)
    with database_subprocess_environment(value) as env:
        previous_database_url = os.environ.get("DATABASE_URL")
        previous_passfile = os.environ.get("PGPASSFILE")
        os.environ["DATABASE_URL"] = env["DATABASE_URL"]
        if "PGPASSFILE" in env:
            os.environ["PGPASSFILE"] = env["PGPASSFILE"]
        try:
            yield env["DATABASE_URL"]
        finally:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url
            if previous_passfile is None:
                os.environ.pop("PGPASSFILE", None)
            else:
                os.environ["PGPASSFILE"] = previous_passfile

@pytest.fixture(scope="session")
def redis_url(request):
    value = request.config.getoption("--redis-url")
    _validate_test_redis(value)
    return value

@pytest.fixture(scope="session")
def db_cli_env(db_url):
    with database_subprocess_environment(db_url) as env:
        yield env


@pytest.fixture(scope="session")
def db_conn(db_url):
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        _assert_effective_database_target(conn)
    except Exception as error:
        pytest.fail(f"Cible PostgreSQL E2E refusée: {error}")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def redis_conn(redis_url):
    try:
        client = redis.Redis.from_url(redis_url)
        settings = client.connection_pool.connection_kwargs
        if settings.get("host") not in _LOCAL_HOSTS or int(settings.get("db", -1)) != 1:
            raise pytest.UsageError("La cible Redis effective ne correspond pas à la base E2E dédiée.")
        guard = client.get(_E2E_REDIS_GUARD_KEY)
        if guard != _E2E_GUARD_TOKEN.encode():
            raise pytest.UsageError("La cible Redis ne porte pas la sentinelle E2E attendue.")
    except Exception as error:
        pytest.fail(f"Cible Redis E2E refusée: {error}")
    try:
        yield client
    finally:
        client.close()

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
                  AND table_name NOT IN ('spatial_ref_sys', '_iddrv_e2e_guard')
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
    """Flush only the verified, dedicated Redis E2E database."""
    def _flush_all():
        try:
            if redis_conn.get(_E2E_REDIS_GUARD_KEY) != _E2E_GUARD_TOKEN.encode():
                raise pytest.UsageError("Sentinelle Redis E2E absente avant nettoyage.")
            redis_conn.flushdb()
            redis_conn.set(_E2E_REDIS_GUARD_KEY, _E2E_GUARD_TOKEN)
        except Exception as error:
            pytest.fail(f"Nettoyage Redis E2E impossible: {error}")

    _flush_all()
    yield
    _flush_all()
