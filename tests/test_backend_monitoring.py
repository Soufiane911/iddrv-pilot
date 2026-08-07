import importlib
import logging
import os
import re

import psycopg2
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import Identity, create_session_token


def _real_session_is_active():
    importlib.reload(__import__("backend.app.auth_repository", fromlist=["auth_repository"]))
    from backend.app.auth_repository import session_is_active
    return session_is_active


@pytest.fixture
def client():
    return TestClient(app)


def _bearer(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def _count_metric(metrics_text: str, metric_name: str) -> int:
    return len([line for line in metrics_text.splitlines()
                if line.startswith(metric_name) and not line.startswith("#")])


def _has_metric(metrics_text: str, metric_name: str) -> bool:
    return any(line.startswith(metric_name) for line in metrics_text.splitlines()
               if not line.startswith("#"))


class TestSessionValidation:
    def test_session_inactive_when_db_unavailable_in_production(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SESSION_SECRET", "p" * 40)
        monkeypatch.setenv("SESSION_FAIL_OPEN", "false")
        from backend.app.config import Settings
        monkeypatch.setattr("backend.app.config.settings", Settings.from_env())

        def raise_db_error(*args, **kwargs):
            raise psycopg2.Error("connection refused")

        monkeypatch.setattr("backend.app.auth_repository.get_connection", lambda: _failing_context(raise_db_error))

        identity = Identity("u1", "a@b.test", "User", "analyst", (1,), session_id="sid-1")
        token, _ = create_session_token(identity)
        session_is_active = _real_session_is_active()
        assert session_is_active(identity, token) is False

    def test_session_active_when_db_unavailable_and_fail_open_configured(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SESSION_FAIL_OPEN", "true")
        from backend.app.config import Settings
        monkeypatch.setattr("backend.app.config.settings", Settings.from_env())

        def raise_db_error(*args, **kwargs):
            raise psycopg2.Error("connection refused")

        monkeypatch.setattr("backend.app.auth_repository.get_connection", lambda: _failing_context(raise_db_error))

        identity = Identity("u1", "a@b.test", "User", "analyst", (1,), session_id="sid-1")
        token, _ = create_session_token(identity)
        session_is_active = _real_session_is_active()
        assert session_is_active(identity, token) is True

    def test_session_inactive_by_default_when_db_fails(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SESSION_FAIL_OPEN", "false")
        from backend.app.config import Settings
        monkeypatch.setattr("backend.app.config.settings", Settings.from_env())

        def raise_db_error(*args, **kwargs):
            raise psycopg2.Error("connection refused")

        monkeypatch.setattr("backend.app.auth_repository.get_connection", lambda: _failing_context(raise_db_error))

        identity = Identity("u1", "a@b.test", "User", "analyst", (1,), session_id="sid-1")
        token, _ = create_session_token(identity)
        session_is_active = _real_session_is_active()
        assert session_is_active(identity, token) is False

    def test_anonymous_session_is_always_active(self):
        session_is_active = _real_session_is_active()
        identity = Identity("anon", "", "Anonymous", "viewer", (), anonymous=True)
        assert session_is_active(identity, "any-token") is True

    def test_session_without_session_id_is_rejected(self):
        session_is_active = _real_session_is_active()
        identity = Identity("u1", "a@b.test", "User", "analyst", (1,))
        assert session_is_active(identity, "any-token") is False


class TestRequestId:
    def test_response_includes_x_request_id(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    def test_error_response_includes_x_request_id(self, client, monkeypatch):
        monkeypatch.setattr("backend.app.api.incidents.get_incident", lambda *args, **kwargs: None)
        response = client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
        body = response.json()
        assert "request_id" in body["error"]
        assert body["error"]["request_id"] == response.headers["X-Request-ID"]

    def test_validation_error_includes_x_request_id(self, client):
        response = client.get("/api/v1/machines/7/timeline?bucket=hour")
        assert response.status_code == 422
        assert "X-Request-ID" in response.headers
        body = response.json()
        assert "request_id" in body["error"]
        assert body["error"]["request_id"] == response.headers["X-Request-ID"]

    def test_passes_through_incoming_x_request_id(self, client):
        response = client.get("/health", headers={"X-Request-ID": "inbound-custom-id"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "inbound-custom-id"

    def test_success_response_has_no_error_body(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "error" not in response.json()


class TestStructuredLogging:
    def test_request_logged_with_request_id(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="iddrv.request"):
            response = client.get("/health")
            request_id = response.headers["X-Request-ID"]

        records = [r for r in caplog.records if r.name == "iddrv.request"]
        assert len(records) >= 1
        log_record = records[-1]
        assert log_record.request_id == request_id
        assert log_record.method == "GET"
        assert log_record.path == "/health"
        assert log_record.status == 200
        assert isinstance(log_record.duration_ms, float)

    def test_error_logged_at_warning_level(self, client, caplog, monkeypatch):
        monkeypatch.setattr("backend.app.api.incidents.get_incident", lambda *args, **kwargs: None)
        with caplog.at_level(logging.WARNING, logger="iddrv.request"):
            client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000099")

        records = [r for r in caplog.records if r.name == "iddrv.request"]
        assert len(records) >= 1
        assert records[-1].levelno == logging.WARNING
        assert records[-1].status == 404

    def test_server_error_logged_at_error_level(self, client, caplog, monkeypatch):
        def failing_check():
            raise RuntimeError("simulated crash")
        monkeypatch.setattr("backend.app.main.check_connection", failing_check)

        with caplog.at_level(logging.ERROR, logger="iddrv.request"):
            client.get("/health")

        records = [r for r in caplog.records if r.name == "iddrv.request"]
        assert len(records) >= 1
        assert records[-1].levelno == logging.ERROR
        assert records[-1].status == 500


class TestMetricsEndpoint:
    def test_metrics_endpoint_returns_200(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_do_not_leak_business_data(self, client):
        response = client.get("/metrics")
        body = response.text
        assert len(body) > 0, "metrics endpoint should return data"
        for forbidden in [
            "incident_id", "user_id", "machine_id", "site_id",
            "erp_ref", "production_order", "order_id",
            "email", "password", "token", "session",
        ]:
            assert forbidden not in body, f"metrics leak business data: {forbidden}"

    def test_required_metric_names_present(self, client):
        response = client.get("/metrics")
        body = response.text
        assert "iddrv_requests_total" in body
        assert "iddrv_http_status_total" in body
        assert "iddrv_request_duration_seconds" in body
        assert "iddrv_investigations_total" in body
        assert "iddrv_database_up" in body

    def test_request_counter_has_data(self, client):
        client.get("/health")
        response = client.get("/metrics")
        body = response.text
        assert _has_metric(body, "iddrv_requests_total")

    def test_http_status_counter_has_data(self, client):
        response = client.get("/metrics")
        body = response.text
        assert _has_metric(body, "iddrv_http_status_total")

    def test_duration_histogram_has_data(self, client):
        client.get("/health")
        response = client.get("/metrics")
        body = response.text
        assert _has_metric(body, "iddrv_request_duration_seconds_bucket")

    def test_database_up_gauge_has_data(self, client):
        response = client.get("/metrics")
        body = response.text
        assert "iddrv_database_up" in body

    def test_metrics_require_token_when_configured(self, client, monkeypatch):
        from dataclasses import replace
        from backend.app import config, metrics, security

        locked = replace(security.settings, metrics_token="scrape-secret", metrics_public=False)
        monkeypatch.setattr(security, "settings", locked)
        monkeypatch.setattr(config, "settings", locked)
        monkeypatch.setattr(metrics, "settings", locked)

        denied = client.get("/metrics")
        assert denied.status_code == 401
        assert denied.json()["error"]["message"] == "metrics_unauthorized"

        wrong = client.get("/metrics", headers={"X-Metrics-Token": "nope"})
        assert wrong.status_code == 401

        ok = client.get("/metrics", headers={"X-Metrics-Token": "scrape-secret"})
        assert ok.status_code == 200
        assert "iddrv_requests_total" in ok.text

        bearer = client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
        assert bearer.status_code == 200

    def test_metrics_allow_admin_session_without_token_header(self, client, monkeypatch):
        from dataclasses import replace
        from backend.app import config, metrics, security

        locked = replace(security.settings, metrics_token="scrape-secret", metrics_public=False)
        monkeypatch.setattr(security, "settings", locked)
        monkeypatch.setattr(config, "settings", locked)
        monkeypatch.setattr(metrics, "settings", locked)

        admin = Identity("admin-1", "admin@test", "Admin", "admin", (1,), session_id="sid-admin")
        ok = client.get("/metrics", headers=_bearer(admin))
        assert ok.status_code == 200

        analyst = Identity("a1", "a@test", "Analyst", "analyst", (1,), session_id="sid-a")
        denied = client.get("/metrics", headers=_bearer(analyst))
        assert denied.status_code == 401

    def test_metrics_closed_in_non_public_mode_without_admin(self, client, monkeypatch):
        from dataclasses import replace
        from backend.app import config, metrics, security

        locked = replace(security.settings, metrics_token="", metrics_public=False)
        monkeypatch.setattr(security, "settings", locked)
        monkeypatch.setattr(config, "settings", locked)
        monkeypatch.setattr(metrics, "settings", locked)

        denied = client.get("/metrics")
        assert denied.status_code == 401


class TestHealthContinuesToWork:
    def test_health_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("ok", "degraded")
        assert response.json()["service"] == "IDDVR API"

    def test_health_degraded_when_db_down(self, client, monkeypatch):
        monkeypatch.setattr("backend.app.main.check_connection", lambda: False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["database"] == "unavailable"


def _failing_context(exception_factory):
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        raise exception_factory()
        yield
    return _ctx()
