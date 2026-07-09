"""Small synchronous PostgreSQL boundary used by API health checks."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection

from .config import settings


def connect() -> connection:
    return psycopg2.connect(
        settings.database_url,
        connect_timeout=settings.db_connect_timeout_s,
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
