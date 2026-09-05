import base64
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app
from backend.app.security import Identity, create_session_token, require_site_roles


client = TestClient(app)


def _token_without_sid(secret: str) -> str:
    payload = {
        "sub": "forged-admin",
        "email": "forged@example.test",
        "name": "Forged",
        "role": "admin",
        "sites": [1],
        "site_roles": {"1": "admin"},
        "exp": int(time.time()) + 3600,
        "nonce": "test",
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{body}.{signature}"


@pytest.mark.parametrize("environment", ["pilot", "prod", "production"])
def test_secure_environment_requires_explicit_session_secret(monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://api:password@db/iddrv")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings.from_env()


def test_secure_environment_forces_session_fail_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://api:password@db/iddrv")
    monkeypatch.setenv("SESSION_SECRET", "a" * 40)
    monkeypatch.setenv("SESSION_FAIL_OPEN", "true")
    assert Settings.from_env().session_fail_open is False


def test_invalid_bearer_is_rejected_before_business_query(monkeypatch):
    monkeypatch.setattr(
        "backend.app.api.sites.list_sites",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("query must not run")),
    )
    response = client.get("/api/v1/sites", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "invalid_token"


def test_malformed_base64_token_is_rejected():
    response = client.get(
        "/api/v1/sites", headers={"Authorization": "Bearer !!!.%%%"}
    )
    assert response.status_code == 401


def test_anonymous_reads_are_disabled_by_default(monkeypatch):
    from backend.app import security

    monkeypatch.setattr(
        security,
        "settings",
        Settings(session_secret="s" * 40, app_environment="development"),
    )
    response = client.get("/api/v1/sites")
    assert response.status_code == 401


def test_signed_token_without_session_id_is_rejected(monkeypatch):
    from backend.app import security

    token = _token_without_sid(security.settings.session_secret)
    response = client.get("/api/v1/sites", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_revoked_session_is_rejected_on_read(monkeypatch):
    identity = Identity("u1", "u@example.test", "User", "viewer", (1,), "session-1")
    from backend.app.security import create_session_token

    token, _ = create_session_token(identity)
    monkeypatch.setattr("backend.app.auth_repository.session_is_active", lambda *_: False)
    response = client.get("/api/v1/sites", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "session_revoked"


def test_roles_are_enforced_per_site():
    identity = Identity(
        "u1",
        "u@example.test",
        "User",
        "analyst",
        (1, 2),
        site_roles=((1, "viewer"), (2, "analyst")),
    )
    with pytest.raises(HTTPException) as forbidden:
        require_site_roles(identity, 1, "analyst")
    assert forbidden.value.status_code == 403
    require_site_roles(identity, 2, "analyst")

    with pytest.raises(HTTPException) as hidden:
        require_site_roles(identity, 3, "viewer")
    assert hidden.value.status_code == 404


def test_workspace_role_is_checked_for_the_target_site(monkeypatch):
    identity = Identity(
        "u1", "u@example.test", "User", "analyst", (1, 2),
        site_roles=((1, "viewer"), (2, "analyst")),
    )
    token, _ = create_session_token(identity)
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(
        "backend.app.api.workspace.create_import_session",
        lambda site_id, name, user_id: {
            "id": "00000000-0000-0000-0000-000000000001",
            "site_id": site_id,
            "name": name,
            "status": "collecting",
            "summary": {},
            "files": [],
            "created_at": "2026-07-10T00:00:00Z",
            "updated_at": "2026-07-10T00:00:00Z",
        },
    )
    forbidden = client.post(
        "/api/v1/sites/1/import-sessions", headers=headers, json={"name": "site 1"}
    )
    allowed = client.post(
        "/api/v1/sites/2/import-sessions", headers=headers, json={"name": "site 2"}
    )
    assert forbidden.status_code == 403
    assert allowed.status_code == 201


def test_logout_fails_when_revocation_cannot_be_persisted(monkeypatch):
    identity = Identity("u1", "u@example.test", "User", "viewer", (1,), "session-1")
    token, _ = create_session_token(identity)
    monkeypatch.setattr("backend.app.api.auth.revoke_session", lambda *_: False)
    response = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 503


def test_login_fails_when_session_cannot_be_persisted(monkeypatch):
    identity = Identity(
        "u1", "u@example.test", "User", "analyst", (1,),
        site_roles=((1, "analyst"),),
    )
    monkeypatch.setattr("backend.app.api.auth.authenticate", lambda *_: identity)
    monkeypatch.setattr("backend.app.api.auth.save_session", lambda *_: None)
    response = client.post(
        "/api/v1/auth/login", json={"email": "u@example.test", "password": "password"}
    )
    assert response.status_code == 503


def test_login_database_failure_is_not_reported_as_bad_credentials(monkeypatch):
    from backend.app.auth_repository import AuthenticationUnavailable
    from backend.app import login_throttle

    monkeypatch.setattr(login_throttle, "allowed", lambda *_: (True, 0))
    monkeypatch.setattr(
        "backend.app.api.auth.authenticate",
        lambda *_: (_ for _ in ()).throw(AuthenticationUnavailable()),
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": "u@example.test", "password": "password"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "authentication_unavailable"


def _request_from(peer: str, **headers: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
            "client": (peer, 1234),
            "server": ("api", 8000),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_login_client_ip_ignores_forwarded_spoofing_from_direct_clients(monkeypatch):
    from dataclasses import replace
    from backend.app import config, login_throttle

    monkeypatch.setattr(
        config,
        "settings",
        replace(config.settings, trusted_proxy_ips=("10.0.0.2/32",)),
    )
    direct = _request_from(
        "198.51.100.10",
        **{"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.9"},
    )
    assert login_throttle.client_ip(direct) == "198.51.100.10"


def test_login_client_ip_uses_headers_only_from_approved_proxy(monkeypatch):
    from dataclasses import replace
    from backend.app import config, login_throttle

    monkeypatch.setattr(
        config,
        "settings",
        replace(config.settings, trusted_proxy_ips=("10.0.0.2/32",)),
    )
    approved = _request_from("10.0.0.2", **{"X-Forwarded-For": "203.0.113.9"})
    fallback = _request_from("10.0.0.2", **{"X-Real-IP": "203.0.113.10"})
    unapproved = _request_from("10.0.0.3", **{"X-Forwarded-For": "203.0.113.11"})
    assert login_throttle.client_ip(approved) == "203.0.113.9"
    assert login_throttle.client_ip(fallback) == "203.0.113.10"
    assert login_throttle.client_ip(unapproved) == "10.0.0.3"


def test_clear_failure_keeps_shared_origin_key_for_redis(monkeypatch):
    from backend.app import login_throttle

    class FakeRedis:
        def __init__(self):
            self.deleted = []

        def delete(self, *keys):
            self.deleted.extend(keys)

    fake = FakeRedis()
    monkeypatch.setattr(login_throttle, "_redis_client", lambda: fake)
    login_throttle.clear_failure("alice@example.test", "198.51.100.20")
    keys = login_throttle._key("alice@example.test", "198.51.100.20")
    assert fake.deleted == [keys.identity]
    assert keys.origin not in fake.deleted


def test_login_throttle_has_identity_and_origin_quotas(monkeypatch):
    from backend.app import login_throttle

    login_throttle.reset_for_tests()
    monkeypatch.setattr(
        login_throttle,
        "_redis_client",
        lambda: (_ for _ in ()).throw(login_throttle.ThrottleUnavailable()),
    )
    try:
        for _ in range(login_throttle.IDENTITY_MAX_FAILURES):
            login_throttle.record_failure("alice@example.test", "198.51.100.20")
        assert login_throttle.allowed("alice@example.test", "198.51.100.20")[0] is False
        # A NAT-shared origin does not block another identity at the identity limit.
        assert login_throttle.allowed("bob@example.test", "198.51.100.20")[0] is True

        login_throttle.clear_failure("alice@example.test", "198.51.100.20")
        assert login_throttle.allowed("alice@example.test", "198.51.100.20")[0] is True
        for index in range(login_throttle.ORIGIN_MAX_FAILURES - login_throttle.IDENTITY_MAX_FAILURES):
            login_throttle.record_failure(f"spray-{index}@example.test", "198.51.100.20")
        assert login_throttle.allowed("new@example.test", "198.51.100.20")[0] is False
        # Clearing one successful identity never clears the shared origin quota.
        login_throttle.clear_failure("bob@example.test", "198.51.100.20")
        assert login_throttle.allowed("new@example.test", "198.51.100.20")[0] is False
    finally:
        login_throttle.reset_for_tests()


def test_successful_login_clears_identity_quota_but_not_origin_quota(monkeypatch):
    from backend.app import login_throttle

    login_throttle.reset_for_tests()
    monkeypatch.setattr(
        login_throttle,
        "_redis_client",
        lambda: (_ for _ in ()).throw(login_throttle.ThrottleUnavailable()),
    )
    identity = Identity(
        "u1", "valid@example.test", "Valid", "analyst", (1,),
        site_roles=((1, "analyst"),),
    )
    monkeypatch.setattr("backend.app.api.auth.authenticate", lambda *_: identity)
    monkeypatch.setattr("backend.app.api.auth.save_session", lambda *_: "session-1")
    monkeypatch.setattr("backend.app.api.auth.replace_session_token", lambda *_: True)
    real_allowed = login_throttle.allowed
    monkeypatch.setattr(login_throttle, "allowed", lambda *_: (True, 0))
    try:
        for _ in range(login_throttle.IDENTITY_MAX_FAILURES):
            login_throttle.record_failure("valid@example.test", "testclient")
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "valid@example.test", "password": "correct"},
        )
        assert response.status_code == 200
        monkeypatch.setattr(login_throttle, "allowed", real_allowed)
        assert login_throttle.allowed("valid@example.test", "testclient")[0] is True

        for index in range(login_throttle.ORIGIN_MAX_FAILURES - login_throttle.IDENTITY_MAX_FAILURES):
            login_throttle.record_failure(f"other-{index}@example.test", "testclient")
        assert login_throttle.allowed("new@example.test", "testclient")[0] is False
    finally:
        login_throttle.reset_for_tests()


def test_redis_reservation_creates_key_before_setting_bounded_ttl():
    from backend.app import login_throttle

    script = login_throttle._RESERVE_SCRIPT
    increment = "local current = redis.call('INCR', key)"
    expiry = "redis.call('EXPIRE', key, ARGV[3])"
    assert increment in script
    assert expiry in script
    assert script.index(increment) < script.index(expiry)
    assert "tonumber(redis.call('TTL', key)) < 0" in script


def test_login_admission_is_atomic_under_concurrency(monkeypatch):
    from backend.app import login_throttle

    login_throttle.reset_for_tests()
    monkeypatch.setattr(
        login_throttle,
        "_redis_client",
        lambda: (_ for _ in ()).throw(login_throttle.ThrottleUnavailable()),
    )
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            admissions = list(
                pool.map(
                    lambda _: login_throttle.allowed(
                        "concurrent@example.test", "198.51.100.21"
                    ),
                    range(20),
                )
            )
        # In-flight reservations count toward the identity limit; no wave of
        # concurrent requests can all pass the check before authentication.
        assert sum(allowed for allowed, _ in admissions) == login_throttle.IDENTITY_MAX_FAILURES
        for allowed, _ in admissions:
            if allowed:
                login_throttle.record_failure("concurrent@example.test", "198.51.100.21")
        assert login_throttle.allowed("concurrent@example.test", "198.51.100.21")[0] is False
    finally:
        login_throttle.reset_for_tests()


def test_login_is_rate_limited_after_five_failures(monkeypatch):
    from backend.app import login_throttle

    login_throttle.reset_for_tests()
    monkeypatch.setattr(login_throttle, "_redis_client", lambda: (_ for _ in ()).throw(login_throttle.ThrottleUnavailable()))
    monkeypatch.setattr("backend.app.api.auth.authenticate", lambda *_: None)
    try:
        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"email": "limited@example.test", "password": "wrong"},
            )
            for _ in range(6)
        ]
        assert [response.status_code for response in responses[:5]] == [401] * 5
        assert responses[5].status_code == 429
        assert responses[5].headers["Retry-After"]
    finally:
        login_throttle.reset_for_tests()
