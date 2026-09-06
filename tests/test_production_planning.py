from contextlib import contextmanager
from datetime import date, datetime, timezone
import os
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg2
import pytest

from backend.app.api.production_planning import router
from backend.app import planning_repository
from backend.app.main import app as real_app
from backend.app.security import Identity, create_session_token


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def headers(role="supervisor", sites=(1,)):
    identity = Identity("planner-1", "planner@example.test", "Planner", role, sites)
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def test_order_normalization_preserves_leading_zeroes():
    assert planning_repository.normalize_order_number("  0000123  ") == ("0000123", "0000123")
    assert planning_repository.normalize_order_number("AbC-01") == ("AbC-01", "abc-01")


def test_create_work_order_accepts_same_of_on_two_presses(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {"id": uuid4(), "order_number": kwargs["order_number"], "allocations": kwargs["allocations"]}

    monkeypatch.setattr(planning_repository, "create_work_order", fake_create)
    response = client.post(
        "/api/v1/sites/1/work-orders",
        headers=headers(),
        json={
            "order_number": "000012",
            "allocations": [
                {"machine_id": 10, "starts_at": "2026-09-07T08:00:00+02:00", "ends_at": "2026-09-07T10:00:00+02:00"},
                {"machine_id": 11, "starts_at": "2026-09-07T08:00:00+02:00", "ends_at": "2026-09-07T10:00:00+02:00"},
            ],
        },
    )
    assert response.status_code == 201
    assert captured["order_number"] == "000012"
    assert [item["machine_id"] for item in captured["allocations"]] == [10, 11]


def test_write_is_site_scoped_and_viewers_cannot_plan(monkeypatch):
    monkeypatch.setattr(
        planning_repository,
        "create_work_order",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not write")),
    )
    body = {
        "order_number": "OF-1",
        "allocations": [{"machine_id": 1, "starts_at": "2026-09-07T08:00:00Z", "ends_at": "2026-09-07T09:00:00Z"}],
    }
    assert client.post("/api/v1/sites/1/work-orders", headers=headers("viewer"), json=body).status_code == 403
    assert client.post("/api/v1/sites/1/work-orders", headers=headers("supervisor", (2,)), json=body).status_code == 404


def test_real_main_app_mounts_planning_sources_and_ingestion(monkeypatch):
    paths = {route.path for route in real_app.routes}
    assert "/api/v1/sites/{site_id}/planning" in paths
    assert "/api/v1/sites/{site_id}/sources" in paths
    assert "/api/v1/ingestion/cycle-events" in paths

    monkeypatch.setattr(planning_repository, "list_planning_week", lambda **kwargs: {
        "site_id": kwargs["site_id"], "timezone": "UTC", "week_start": kwargs["week_start"], "items": []
    })
    response = TestClient(real_app).get(
        "/api/v1/sites/1/planning?week_start=2026-09-07", headers=headers("viewer")
    )
    assert response.status_code == 200
    assert response.json()["site_id"] == 1


def test_week_read_uses_repository_site_timezone_and_requires_site_access(monkeypatch):
    captured = {}

    def fake_week(**kwargs):
        captured.update(kwargs)
        return {"site_id": kwargs["site_id"], "timezone": "America/Montreal", "week_start": kwargs["week_start"], "items": []}

    monkeypatch.setattr(planning_repository, "list_planning_week", fake_week)
    response = client.get("/api/v1/sites/1/planning?week_start=2026-09-07", headers=headers("viewer"))
    assert response.status_code == 200
    assert captured["week_start"] == date(2026, 9, 7)
    assert response.json()["timezone"] == "America/Montreal"
    assert client.get("/api/v1/sites/1/planning?week_start=2026-09-07", headers=headers("viewer", (2,))).status_code == 404


def test_patch_requires_row_version_and_maps_stale_update_to_409(monkeypatch):
    slot_id = uuid4()
    monkeypatch.setattr(
        planning_repository,
        "get_slot",
        lambda value: {"id": slot_id, "site_id": 1, "status": "planned", "row_version": 4},
    )
    def stale(**kwargs):
        raise planning_repository.PlanningConflict("stale_row_version")
    monkeypatch.setattr(planning_repository, "update_slot", stale)
    response = client.patch(
        f"/api/v1/planning/slots/{slot_id}",
        headers=headers(),
        json={"row_version": 3, "note": "correction"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "stale_row_version"


def test_migration_has_no_manual_quantity_and_enforces_press_overlap():
    sql = open("db/migrations/020_workshop_planning.sql", encoding="utf-8").read()
    assert "UNIQUE (site_id, order_number_normalized)" in sql
    assert "EXCLUDE USING gist" in sql
    assert "tstzrange(starts_at, ends_at, '[)') WITH &&" in sql
    assert "quantity" not in sql.lower()
    assert "row_version" in sql


def test_planning_aggregates_multiple_current_erp_lines_per_press(monkeypatch):
    url = os.getenv("ERP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ERP_TEST_DATABASE_URL dedicated PostgreSQL not supplied")
    parsed = urlparse(url)
    assert parsed.hostname == "db" and parsed.path == "/iddrv_test"

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO sites(name,timezone) VALUES(%s,'UTC') RETURNING id", (f"planning-{uuid4().hex}",))
            site_id = cur.fetchone()[0]
            machine_ref = f"PRESS-{uuid4().hex[:8]}"
            cur.execute(
                "INSERT INTO machines(site_id,erp_ref,name,workshop_code) VALUES(%s,%s,%s,%s) RETURNING id",
                (site_id, machine_ref, machine_ref, machine_ref),
            )
            machine_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO work_orders(site_id,order_number,order_number_normalized) VALUES(%s,'000012','000012') RETURNING id"
                , (site_id,),
            )
            work_order_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO work_order_allocations(site_id,work_order_id,machine_id) VALUES(%s,%s,%s) RETURNING id",
                (site_id, work_order_id, machine_id),
            )
            allocation_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO planning_slots(site_id,allocation_id,machine_id,starts_at,ends_at)
                   VALUES(%s,%s,%s,'2026-09-07 06:00+00','2026-09-07 14:00+00')""",
                (site_id, allocation_id, machine_id),
            )
            cur.execute(
                "INSERT INTO production_orders(site_id,id,started_at) VALUES(%s,'000012','2026-09-07 06:00+00')",
                (site_id,),
            )
            cur.execute(
                "INSERT INTO import_passports(site_id,file_name,file_hash,status) VALUES(%s,'erp.xlsx',%s,'completed') RETURNING id",
                (site_id, uuid4().hex),
            )
            passport_id = cur.fetchone()[0]
            for source_row, produced, good, scrap, cycles in ((1, 10, 9, 1, 5), (2, 20, 18, 2, 10)):
                cur.execute(
                    """INSERT INTO erp_declarations(site_id,machine_id,production_order_id,declaration_key)
                       VALUES(%s,%s,'000012',%s) RETURNING id""",
                    (site_id, machine_id, f"line-{source_row}"),
                )
                declaration_id = cur.fetchone()[0]
                revision_id = str(uuid4())
                cur.execute(
                    """INSERT INTO erp_declaration_revisions
                       (id,site_id,declaration_id,production_order_id,revision_number,passport_id,sheet_name,
                        source_row,recorded_at,shift_started_at,shift_number,order_type,bounds_origin,
                        produced_parts,good_parts,scrap_parts,cycle_count,raw_data,warnings,content_hash)
                       VALUES(%s,%s,%s,'000012',1,%s,'ERP',%s,'2026-09-08 12:00+00',
                              '2026-09-07 06:00+00',%s,'normal','source',%s,%s,%s,%s,'{}','[]',%s)""",
                    (revision_id, site_id, declaration_id, passport_id, source_row, source_row,
                     produced, good, scrap, cycles, f"hash-{source_row}"),
                )
                cur.execute(
                    "UPDATE erp_declarations SET current_revision_id=%s WHERE id=%s",
                    (revision_id, declaration_id),
                )

        @contextmanager
        def same_transaction():
            yield conn

        monkeypatch.setattr(planning_repository, "get_connection", same_transaction)
        row = planning_repository.list_planning_week(site_id=site_id, week_start=date(2026, 9, 7))["items"][0]
        assert (row["produced_parts_erp"], row["good_parts_erp"], row["scrap_parts_erp"], row["cycles_erp"]) == (30, 27, 3, 15)
        assert row["order_total_produced_parts"] == 30
    finally:
        conn.rollback()
        conn.close()
