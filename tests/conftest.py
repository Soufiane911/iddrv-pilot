import os
from dataclasses import replace

import pytest


@pytest.fixture(autouse=True)
def _test_session_fail_open(monkeypatch):
    monkeypatch.setenv("SESSION_FAIL_OPEN", "true")
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setenv("METRICS_PUBLIC", "true")
    monkeypatch.setattr("backend.app.auth_repository.session_is_active", lambda identity, token: True)
    from backend.app import config, metrics, security

    test_settings = replace(
        security.settings,
        app_environment="test",
        allow_anonymous_reads=True,
        metrics_token="",
        metrics_public=True,
    )
    monkeypatch.setattr(security, "settings", test_settings)
    monkeypatch.setattr(config, "settings", test_settings)
    monkeypatch.setattr(metrics, "settings", test_settings)
