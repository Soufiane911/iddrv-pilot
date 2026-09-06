import pytest

from conftest import _validate_test_database, _validate_test_redis
from run_tests import redact_credentials


CONFIRMATION = "iddrv_test:truncate-and-redis-1:flush"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:password@db.example:5432/iddrv_test",
        "postgresql://user:password@localhost:5432/iddrv",
        "postgresql://user:password@localhost:5432/iddrv_test?host=db.example",
        "postgresql://user:password@localhost:5432/iddrv_test?dbname=iddrv_test",
    ],
)
def test_database_cleanup_guard_rejects_ambiguous_targets(monkeypatch, url):
    monkeypatch.setenv("E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION", CONFIRMATION)
    with pytest.raises(pytest.UsageError):
        _validate_test_database(url)


def test_redis_cleanup_guard_rejects_query_override(monkeypatch):
    monkeypatch.setenv("E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION", CONFIRMATION)
    with pytest.raises(pytest.UsageError):
        _validate_test_redis("redis://:password@localhost:6379/1?db=1")


def test_cleanup_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setenv("E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION", "not-confirmed")
    with pytest.raises(pytest.UsageError):
        _validate_test_database("postgresql://user:password@localhost:5432/iddrv_test")


def test_redaction_covers_empty_userinfo_and_sensitive_query_values():
    text = (
        "redis://:redis-secret@localhost:6379/1 "
        "postgresql://user:db-secret@localhost/iddrv_test?sslpassword=query-secret&token=abc"
    )
    redacted = redact_credentials(text)

    assert "redis-secret" not in redacted
    assert "db-secret" not in redacted
    assert "query-secret" not in redacted
    assert "token=abc" not in redacted
    assert redacted.count("***") >= 4
