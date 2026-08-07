import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException
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
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings.from_env()


def test_secure_environment_forces_session_fail_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "pilot")
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
