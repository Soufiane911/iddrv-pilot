import pytest

from backend.app.config import Settings
from ingest.runtime_config import worker_database_url


def test_api_url_is_required_in_secure_environments_even_with_legacy_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.delenv("API_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:password@db/iddrv")
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)

    with pytest.raises(RuntimeError, match="API_DATABASE_URL"):
        Settings.from_env()


def test_api_settings_prefer_dedicated_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://api:password@db/iddrv")
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:password@db/iddrv")
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)

    assert Settings.from_env().database_url == "postgresql://api:password@db/iddrv"


def test_worker_url_is_required_securely_but_owner_fallback_remains_local(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("WORKER_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:password@db/iddrv")

    with pytest.raises(RuntimeError, match="WORKER_DATABASE_URL"):
        worker_database_url()

    monkeypatch.setenv("APP_ENV", "development")
    assert worker_database_url() == "postgresql://owner:password@db/iddrv"
