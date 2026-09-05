from uuid import UUID

from backend.app import repositories


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.sql = ""
        self.args = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.sql = sql
        self.args = args

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return self.cursor_value


def test_get_incident_reads_one_row_and_latest_feedback(monkeypatch):
    row = (
        UUID("00000000-0000-0000-0000-000000000001"), 1, 2, "152", None,
        "open", "high", "short_shot_increase", "short_shot",
        None, None, None, None, "high", "confirmed",
    )
    cursor = _Cursor(row)
    monkeypatch.setattr(repositories, "get_connection", lambda: _Connection(cursor))

    incident = repositories.get_incident(UUID("00000000-0000-0000-0000-000000000001"), allowed_site_ids=(1,))

    assert incident["feedback_verdict"] == "confirmed"
    assert cursor.sql.count("SELECT") == 2  # outer query plus the LATERAL subquery
    assert "LEFT JOIN LATERAL" in cursor.sql
    assert "ORDER BY f.created_at DESC, f.id DESC" in cursor.sql
    assert "i.id=%s" in cursor.sql
    assert cursor.args == ["00000000-0000-0000-0000-000000000001", [1]]


def test_get_incident_does_not_query_when_site_scope_is_empty(monkeypatch):
    def fail_connection():
        raise AssertionError("empty site scope must be rejected before querying")

    monkeypatch.setattr(repositories, "get_connection", fail_connection)

    assert repositories.get_incident(UUID("00000000-0000-0000-0000-000000000001"), allowed_site_ids=()) is None
