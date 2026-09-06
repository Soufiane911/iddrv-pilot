import pytest

from backend.app import connection_repository, planning_repository, site_repository, source_repository


class TraceCursor:
    def __init__(self, *, one=None, many=None):
        self.statements = []
        self._one = list(one or [])
        self._many = many

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return self._one.pop(0) if self._one else None

    def fetchall(self):
        return self._many or []


class TraceConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self, **kwargs):
        return self.cursor_value


def test_archive_machine_locks_site_before_machine_without_join_lock(monkeypatch):
    cursor = TraceCursor(one=[(7,), (7, "active"), (11, 7, "active")])
    monkeypatch.setattr(site_repository, "get_connection", lambda: TraceConnection(cursor))

    site_repository.archive_machine(11)

    assert "FROM machines" in cursor.statements[0][0]
    assert "FOR UPDATE" not in cursor.statements[0][0]
    assert "FROM sites" in cursor.statements[1][0]
    assert "FOR UPDATE" in cursor.statements[1][0]
    assert "FROM machines" in cursor.statements[2][0]
    assert "JOIN" not in cursor.statements[2][0]
    assert "FOR UPDATE" in cursor.statements[2][0]


def test_planning_locks_site_before_machine_without_join_lock():
    cursor = TraceCursor(one=[{"status": "active"}, {"status": "active"}])

    planning_repository._active_machine(cursor, site_id=7, machine_id=11)

    assert len(cursor.statements) == 2
    assert "FROM sites" in cursor.statements[0][0]
    assert "FOR UPDATE" in cursor.statements[0][0]
    assert "FROM machines" in cursor.statements[1][0]
    assert "JOIN" not in cursor.statements[1][0]


def test_save_connection_rechecks_lifecycle_before_upsert(monkeypatch):
    cursor = TraceCursor(one=[
        {"id": 7, "status": "active"},
        {"id": 11, "site_id": 7, "status": "active"},
        None,
        {"id": "connection-1", "site_id": 7, "machine_id": 11},
    ])
    monkeypatch.setattr(connection_repository, "get_connection", lambda: TraceConnection(cursor))

    connection_repository.save_connection(
        {"id": 11, "site_id": 7},
        {
            "base_url": "http://press.test",
            "external_machine_id": "press-11",
            "secret_ref": "PRESS",
            "poll_interval_s": 5,
            "enabled": True,
            "mapping_profile": "iddrv-cycle-v1",
        },
    )

    assert "FROM sites" in cursor.statements[0][0]
    assert "FOR UPDATE" in cursor.statements[0][0]
    assert "FROM machines" in cursor.statements[1][0]
    assert "FOR UPDATE" in cursor.statements[1][0]
    assert "INSERT INTO machine_connections" in cursor.statements[3][0]


def test_save_connection_never_upserts_an_archived_machine(monkeypatch):
    cursor = TraceCursor(one=[
        {"id": 7, "status": "active"},
        {"id": 11, "site_id": 7, "status": "archived"},
    ])
    monkeypatch.setattr(connection_repository, "get_connection", lambda: TraceConnection(cursor))

    with pytest.raises(connection_repository.ConnectionConflict, match="machine_archived"):
        connection_repository.save_connection(
            {"id": 11, "site_id": 7},
            {"base_url": "http://press.test", "external_machine_id": "press-11",
             "secret_ref": "PRESS", "poll_interval_s": 5, "enabled": True,
             "mapping_profile": "iddrv-cycle-v1"},
        )

    assert not any("INSERT INTO machine_connections" in statement for statement, _ in cursor.statements)


def test_replay_rejects_archived_receipt_and_continues(monkeypatch):
    cursor = TraceCursor(many=[{"id": "archived"}, {"id": "live"}])
    seen = []

    def materialize(cur, receipt, *, terminal_archived):
        seen.append((receipt["id"], terminal_archived))
        if receipt["id"] == "archived":
            source_repository._set_receipt_rejected(cur, receipt["id"], reason="machine_archived", machine_id=11)
            return False
        return True

    monkeypatch.setattr(source_repository, "_materialize_receipt", materialize)

    assert source_repository.replay_pending_receipts_in_transaction(cursor, site_id=7) == 1
    assert seen == [("archived", True), ("live", True)]
    assert "state='rejected'" in cursor.statements[1][0]
