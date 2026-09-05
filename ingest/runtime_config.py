"""Database URL selection for ingestion processes."""

from __future__ import annotations

import os


_SECURE_ENVIRONMENTS = {"pilot", "prod", "production"}
_DEFAULT_DATABASE_URL = "postgresql://iddrv_user@localhost:5432/iddrv"


def worker_database_url() -> str:
    """Return the worker URL, with an owner fallback only for local development."""
    environment = os.getenv("APP_ENV", "development").strip().lower()
    configured = os.getenv("WORKER_DATABASE_URL", "").strip()
    if environment in _SECURE_ENVIRONMENTS and not configured:
        raise RuntimeError("WORKER_DATABASE_URL must be explicitly configured in pilot/production")
    return configured or os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)
