from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api import site_management
from backend.app.security import Identity, create_session_token


client = TestClient(app)


def headers(role="supervisor", sites=(1,)):
    token, _ = create_session_token(Identity(str(uuid4()), "site@example.com", "Site", role, tuple(sites), site_roles=tuple((site, role) for site in sites)))
    return {"Authorization": f"Bearer {token}"}


def test_site_creation_requires_supervisor_and_assigns_creator(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return {"id": 9, "name": kwargs["name"], "timezone": kwargs["timezone"]}

    monkeypatch.setattr(site_management, "create_site", create)
    assert client.post("/api/v1/sites", json={"name": "Atelier Nantes"}).status_code == 401
    assert client.post("/api/v1/sites", headers=headers("analyst"), json={"name": "Atelier Nantes"}).status_code == 403
    response = client.post("/api/v1/sites", headers=headers(), json={"name": "  Atelier Nantes  "})
    assert response.status_code == 201
    assert response.json()["id"] == 9
    assert calls[0]["name"] == "  Atelier Nantes  "
    assert calls[0]["creator_role"] == "supervisor"


def test_site_creation_conflict_is_public(monkeypatch):
    monkeypatch.setattr(site_management, "create_site", lambda **kwargs: (_ for _ in ()).throw(site_management.SiteConflict("site_name_already_exists")))
    response = client.post("/api/v1/sites", headers=headers(), json={"name": "Atelier Nantes"})
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "site_name_already_exists"


def test_site_deletion_is_admin_only_and_protects_last_site(monkeypatch):
    calls = []
    monkeypatch.setattr(site_management, "delete_site", lambda site_id: calls.append(site_id))
    assert client.delete("/api/v1/sites/2", headers=headers("supervisor")).status_code == 403
    assert client.delete("/api/v1/sites/2", headers=headers("admin")).status_code == 204
    assert calls == [2]
    monkeypatch.setattr(site_management, "delete_site", lambda site_id: (_ for _ in ()).throw(site_management.SiteConflict("last_site_cannot_be_deleted")))
    response = client.delete("/api/v1/sites/1", headers=headers("admin"))
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "last_site_cannot_be_deleted"


def test_explicit_site_archive_has_rbac_and_stable_errors(monkeypatch):
    calls = []
    monkeypatch.setattr(site_management, "archive_site", lambda site_id: calls.append(site_id))
    assert client.post("/api/v1/sites/2/archive", headers=headers("supervisor")).status_code == 403
    assert client.post("/api/v1/sites/2/archive", headers=headers("admin")).status_code == 204
    assert calls == [2]

    monkeypatch.setattr(site_management, "archive_site", lambda site_id: (_ for _ in ()).throw(site_management.SiteNotFound("site_not_found")))
    missing = client.post("/api/v1/sites/404/archive", headers=headers("admin"))
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "site_not_found"

    monkeypatch.setattr(site_management, "archive_site", lambda site_id: (_ for _ in ()).throw(site_management.SiteConflict("site_already_archived")))
    conflict = client.post("/api/v1/sites/2/archive", headers=headers("admin"))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["message"] == "site_already_archived"
