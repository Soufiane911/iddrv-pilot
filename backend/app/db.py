"""Small synchronous PostgreSQL boundary used by API health checks."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection

try:
    import redis
except ImportError:  # pragma: no cover - declared backend dependency
    redis = None  # type: ignore[assignment]

from . import config


def connect() -> connection:
    return psycopg2.connect(
        config.settings.database_url,
        connect_timeout=config.settings.db_connect_timeout_s,
    )


@contextmanager
def get_connection() -> Iterator[connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def check_connection() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except (psycopg2.Error, OSError):
        return False


def check_redis_connection() -> bool:
    """Check the Redis dependency without leaking connection details."""
    if redis is None:
        return False
    try:
        client = redis.Redis.from_url(
            config.settings.redis_url,
            socket_connect_timeout=config.settings.db_connect_timeout_s,
            socket_timeout=config.settings.db_connect_timeout_s,
        )
        return bool(client.ping())
    except Exception:  # redis-py has multiple connection and protocol errors
        return False
